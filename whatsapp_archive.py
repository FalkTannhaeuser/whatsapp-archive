#!/usr/bin/python3

"""Reads a WhatsApp conversation export file and writes a HTML file."""

import argparse
import datetime
import dateutil.parser
import itertools
import jinja2
import logging
import os.path
import re
import yaml
import locale
import glob
import os
import collections
import pandas as pd


# Format of the standard WhatsApp export line. This is likely to change in the
# future and so this application will need to be updated.
DATE_RE = '(?P<date>[\d/\.-]+)'
TIME_RE = '(?P<time>[\d:]+( [AP]M)?)'
DATETIME_RE = '\[?' + DATE_RE + ',? ' + TIME_RE + '\]?'
SEPARATOR_RE = '( - |: | )'
NAME_RE = '(?P<name>[^:]+)'
WHATSAPP_RE = (DATETIME_RE +
               SEPARATOR_RE +
               NAME_RE +
               ': '
               '(?P<body>.*$)')

FIRSTLINE_RE = (DATETIME_RE +
               SEPARATOR_RE +
               '(?P<body>.*$)')


class Error(Exception):
    """Something bad happened."""


def ParseLine(line):
    """Parses a single line of WhatsApp export file."""
    m = re.match(WHATSAPP_RE, line)
    if m:
        d = dateutil.parser.parse("%s %s" % (m.group('date'),
            m.group('time')), dayfirst=True)
        return d, m.group('name'), m.group('body')
    # Maybe it's the first line which doesn't contain a person's name.
    m = re.match(FIRSTLINE_RE, line)
    if m:
        d = dateutil.parser.parse("%s %s" % (m.group('date'),
            m.group('time')), dayfirst=True)
        return d, "nobody", m.group('body')
    return None


def IdentifyMessages(lines, mlist=None):
    """Input text can contain multi-line messages. If there's a line that
    doesn't start with a date and a name, that's probably a continuation of the
    previous message and should be appended to it.
    """
    messages = []
    msg_date = None
    msg_user = None
    msg_body = None
    for line in lines:
        m = ParseLine(line)
        if m is not None:
            if msg_date is not None:
                # We have a new message, so there will be no more lines for the
                # one we've seen previously -- it's complete. Let's add it to
                # the list.
                if mlist is not None and msg_body.endswith('<Medien ausgeschlossen>'):
                    med = mlist[msg_date].pop(0)
                    msg_body = msg_body.replace('<Medien ausgeschlossen>',
                                                med + ' (Datei angehängt)')
                    # print(msg_date, msg_body)
                messages.append((msg_date, msg_user, msg_body))
            msg_date, msg_user, msg_body = m
        else:
            if msg_date is None:
                raise Error("Can't parse the first line: " + repr(line) +
                        ', regexes are FIRSTLINE_RE=' + repr(FIRSTLINE_RE) +
                        ' and WHATSAPP_RE=' + repr(WHATSAPP_RE))
            msg_body += '\n' + line.strip()
    # The last message remains. Let's add it, if it exists.
    if msg_date is not None:
        messages.append((msg_date, msg_user, msg_body))
    return messages


def TemplateData(messages, input_filename, toc_data):
    """Create a struct suitable for processing in a template.
    Returns:
        A dictionary of values.
    """
    by_user = []
    file_basename = os.path.basename(input_filename)
    for user, msgs_of_user in itertools.groupby(messages, lambda x: x[1]):
        by_user.append((user, list(msgs_of_user)))
    return dict(by_user=by_user, input_basename=file_basename,
            input_full_path=input_filename, toc_data=toc_data)


def FormatHTML(data, timestamp_str):
    tmpl = """<!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp archive {{ input_basename }}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: sans-serif;
                font-size: 10px;
            }
            img {
                padding: 0;
                display: block;
                margin: 0 auto;
                max-height: 100%;
                max-width: 100%;
            }
            ol.users {
                list-style-type: none;
                list-style-position: inside;
                margin: 0;
                padding: 0;
            }
            ol.messages {
                list-style-type: none;
                list-style-position: inside;
                margin: 0;
                padding: 0;
            }
            ol.messages li {
                margin-left: 1em;
                font-size: 12px;
            }
            span.username {
                color: gray;
            }
            span.date {
                color: gray;
            }
        </style>
    </head>
    <body>
        <a name="top"></a>
        
        <h1>{{ input_basename }}, Stand vom {{ timestamp_str }}</h1>
        
        <h2>Links</h2>
        <ol class="messages">
        {% for item in toc_data["link_list"] %}
            <li><a href="{{ item["target"] }}">{{ item["text"] }}</a></li>
        {% endfor %}
        </ol>

        <h2>{{ toc_data["title"] }}</h2>
        <ol class="messages">
        {% for item in toc_data["toc"] %}
            <li><a href="#{{ item["anchor"] }}">{{ item["text"] }}</a></li>
        {% endfor %}
        </ol>
        <h2>Chat-Archiv</h2>
        <ol class="users">
        {% for user, messages in by_user %}
            <li>
            <a name="{{ user }} {{ messages[0][0] }}"></a>
            <span class="username">{{ user }}</span>
            <span class="date">{{ messages[0][0] }}</span>
            <ol class="messages">
            {% for message in messages %}
                <li>{{ message[2] | e }}</li>
            {% endfor %}
            </ol>
            &nbsp;&nbsp;&nbsp;&nbsp;<a href="#top">Zurück nach oben</a>
            </li>
        {% endfor %}
        </ol>
    </body>
    </html>
    """
    return jinja2.Environment().from_string(tmpl).render(timestamp_str=timestamp_str,
                                                         **data)

def media_list(media_dir):
    def sort_file_key(f):
        base, ext = os.path.splitext(f)
        if base.endswith(')'):
            return f
        else:
            return base + ' (0)' + ext
        
    result = collections.defaultdict(list)
    if media_dir is not None:
        for f in sorted(glob.glob(os.path.join(media_dir, '*')), key=sort_file_key):
            if ' ' in f:
                new_f = f.replace(' ', '_')
                os.rename(f, new_f)
                f = new_f
            a = re.findall(r'(\d\d\d\d-\d\d-\d\d)_at_(\d\d\.\d\d)\.\d\d',
                           os.path.basename(f))
            if len(a) == 1 and len(a[0]) == 2:
                result[dateutil.parser.parse(a[0][0] + ' ' + a[0][1].replace('.', ':'))].append(f.replace(os.sep, '/'))
            else:
                print(f'Ignoring file {f}')
    return result


def _insert_dedup(df):
    df.insert(2, 'dedup', 0)
    dup_cnt = collections.Counter()
    for idx, row in df.iterrows():
        dup_cnt[(row.date, row.user)] += 1
        df.at[idx, 'dedup'] = dup_cnt[(row.date, row.user)]
    return df


def merge_input_files(input1, input2, mlist):
    with open(input1, 'rt', encoding='utf-8') as i1fd:
        messages1 = IdentifyMessages(i1fd.readlines())
    with open(input2, 'rt', encoding='utf-8') as i2fd:
        messages2 = IdentifyMessages(i2fd.readlines())
    df1 = _insert_dedup(pd.DataFrame(messages1, columns=['date', 'user', 'body']))
    df2 = _insert_dedup(pd.DataFrame(messages2, columns=['date', 'user', 'body']))
    df = pd.merge(df1, df2, how='outer', on=['date', 'user', 'dedup'], sort=False)
    msg_list = []
    for idx, row in df.iterrows():
        if pd.isna(row.body_x):
            if row.body_y.endswith('<Medien ausgeschlossen>'):
                med = mlist[row.date].pop(0)
                msg_body = row.body_y.replace('<Medien ausgeschlossen>',
                                              med + ' (Datei angehängt)')
            else:
                msg_body = row.body_y
        elif pd.isna(row.body_y):
            if row.body_x.endswith('<Medien ausgeschlossen>'):
                med = mlist[row.date].pop(0)
                msg_body = row.body_x.replace('<Medien ausgeschlossen>',
                                              med + ' (Datei angehängt)')
            else:
                msg_body = row.body_x
        elif row.body_x.endswith('<Medien ausgeschlossen>'):
            med = mlist[row.date].pop(0)
            msg_body = row.body_x.replace('<Medien ausgeschlossen>',
                                          f'{med} (Datei angehängt)\n{row.body_y}')
        elif row.body_y.endswith('<Medien ausgeschlossen>'):
            med = mlist[row.date].pop(0)
            msg_body = row.body_y.replace('<Medien ausgeschlossen>',
                                          f'{med} (Datei angehängt)\n{row.body_x}')
        else:
            msg_body = row.body_x if len(row.body_x) > len(row.body_y) else row.body_y
        msg_list.append((row.date, row.user, msg_body))
    return msg_list


def main():
    locale.setlocale(locale.LC_ALL, 'de_DE')
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Produce a browsable history '
            'of a WhatsApp conversation')
    parser.add_argument('-i', dest='input_file', required=True)
    parser.add_argument('-i2', dest='input_file2', default=None)
    parser.add_argument('-toc', dest='toc_file', default=None)
    parser.add_argument('-o', dest='output_file', required=True)
    parser.add_argument('-m', dest='media_dir', default=None)
    args = parser.parse_args()
    mlist = media_list(args.media_dir)
    if args.input_file2 is None:
        with open(args.input_file, 'rt', encoding='utf-8-sig') as fd:
            messages = IdentifyMessages(fd.readlines(), mlist)
    else:
        messages = merge_input_files(args.input_file, args.input_file2, mlist)
    if args.toc_file is None:
        toc_data = dict(title="", toc=[])
    else:
        with open(args.toc_file, 'rt', encoding='utf8') as fd:
            toc_data = yaml.load(fd, yaml.SafeLoader)
    template_data = TemplateData(messages, args.input_file, toc_data)
    input_stat = os.stat(args.input_file)
    timestamp_str = datetime.datetime.fromtimestamp(input_stat.st_ctime).strftime('%A, %x, %H:%M Uhr')
    HTML = FormatHTML(template_data, timestamp_str)
    HTML = re.sub(r'<li>\u200E?(.*\.mp4) \(Datei angehängt\)',
                  r'<li><video controls><source src="\1" type="video/mp4">Video kann nicht angezeigt werden.</video>', HTML)
    HTML = re.sub(r'<li>\u200E?(.*\.opus|.*\.ogg) \(Datei angehängt\)',
                  r'<li><audio controls><source src="\1">Audio kann nicht wiedergegeben werden.</audio>', HTML)
    HTML = re.sub(r'<li>\u200E?(.*\.vcf) \(Datei angehängt\)', r'<li><a href="\1">\1</a>', HTML)
    HTML = re.sub(r'<li>\u200E?(.*) \(Datei angehängt\)', r'<li><img src="\1">', HTML)
    HTML = re.sub(r'(https?://[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&/=;]*)',
                  r'<a href="\1" target="_blank" rel="noopener">\1</a>', HTML)

    with open(args.output_file, 'w', encoding='utf-8') as fd:
        fd.write(HTML)


if __name__ == '__main__':
    main()
