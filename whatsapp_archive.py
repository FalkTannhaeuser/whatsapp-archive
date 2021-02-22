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


def IdentifyMessages(lines):
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
    """Create a struct suitable for procesing in a template.
    Returns:
        A dictionary of values.
    """
    by_user = []
    file_basename = os.path.basename(input_filename)
    for user, msgs_of_user in itertools.groupby(messages, lambda x: x[1]):
        by_user.append((user, list(msgs_of_user)))
    return dict(by_user=by_user, input_basename=file_basename,
            input_full_path=input_filename, toc_data=toc_data)


def FormatHTML(data):
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
    timestamp_str = datetime.datetime.now().strftime('%A, %x, %H:%M Uhr')
    return jinja2.Environment().from_string(tmpl).render(timestamp_str=timestamp_str,
                                                         **data)


def main():
    locale.setlocale(locale.LC_ALL, 'de_DE')
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Produce a browsable history '
            'of a WhatsApp conversation')
    parser.add_argument('-i', dest='input_file', required=True)
    parser.add_argument('-toc', dest='toc_file', default=None)
    parser.add_argument('-o', dest='output_file', required=True)
    args = parser.parse_args()
    with open(args.input_file, 'rt', encoding='utf-8-sig') as fd:
        messages = IdentifyMessages(fd.readlines())
    if args.toc_file is None:
        toc_data = dict(title="", toc=[])
    else:
        with open(args.toc_file, 'rt', encoding='utf8') as fd:
            toc_data = yaml.load(fd, yaml.SafeLoader)
    template_data = TemplateData(messages, args.input_file, toc_data)
    HTML = FormatHTML(template_data)
    HTML = re.sub(r'<li>\u200E?(.*\.mp4) \(Datei angehängt\)',
                  r'<li><video autoplay muted controls><source src="\1" type="video/mp4">Video kann nicht angezeigt werden.</video>', HTML)
    HTML = re.sub(r'<li>\u200E?(.*\.opus) \(Datei angehängt\)',
                  r'<li><audio controls><source src="\1">Audio kann nicht wiedergegeben werden.</audio>', HTML)
    HTML = re.sub(r'<li>\u200E?(.*) \(Datei angehängt\)', r'<li><img src="\1">', HTML)
    HTML = re.sub(r'(https?://[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&/=;]*)',
                  r'<a href="\1" target="_blank" rel="noopener">\1</a>', HTML)

    with open(args.output_file, 'w', encoding='utf-8') as fd:
        fd.write(HTML)


if __name__ == '__main__':
    main()
