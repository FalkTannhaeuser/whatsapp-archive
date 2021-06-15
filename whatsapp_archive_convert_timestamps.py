# -*- coding: utf-8 -*-
"""
Created on Mon Jun 14 14:30:02 2021

@author: falkt
"""
import whatsapp_archive
import re

with open(r'C:\Users\falkt\OneDrive\Bilder\KlassentreffenWolgast\WhatsApp Chat mit Klasse 10 b „Treffen“ 4a.txt', 'rt', encoding='utf-8') as ifd, \
    open(r'C:\Users\falkt\OneDrive\Bilder\KlassentreffenWolgast\WhatsApp Chat mit Klasse 10 b „Treffen“ 4a_out.txt', 'wt', encoding='utf-8') as ofd:
        for iline in ifd:
            rslt = whatsapp_archive.ParseLine(re.sub(r'\[(.*), (.*)\]', r'\2, \1 -', iline))
            if rslt is None:
                oline = iline.strip()
            else:
                dt, usr, body = rslt    
                oline = f"{dt.strftime('%d.%m.%y, %H:%M -')} {usr}: {body}"
            print(oline, file=ofd)
        