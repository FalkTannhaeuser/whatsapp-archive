# -*- coding: utf-8 -*-
"""
Created on Tue Jun 15 02:00:38 2021

@author: falkt
"""
from ftplib import FTP, error_perm
import os
import glob
import colorama


colorama.init(autoreset=True, strip=False)
local_root = r'C:\Users\falkt\OneDrive\Bilder\KlassentreffenWolgast'
ftp = FTP('falk.tannhauser.free.fr')
print(ftp.getwelcome())
ftp.login('falk.tannhauser', 'wiewiork')
for d in ('Klasse_10_b-Dateien',
          # 'WhatsApp_Media',
          ):
    try:
        ftp.mkd(d)
    except error_perm as ex:
        print(ex)
    ftp.cwd(d)
    print(f'{colorama.Fore.RED}/{d}{colorama.Style.RESET_ALL} before uploading:')
    ftp.dir()
    for f in glob.glob(os.path.join(local_root, d, '*')):
        with open(f, 'rb') as fd:
            ftp.storbinary(f'STOR {os.path.basename(f)}', fd)
    print(f'{colorama.Fore.RED}/{d}{colorama.Style.RESET_ALL} after uploading:')
    ftp.dir()
    ftp.cwd('..')
print(f'{colorama.Fore.RED}/{colorama.Style.RESET_ALL} before uploading:')
ftp.dir()
for f in ('Klasse_10_b.html', 'index.html'):
    with open(os.path.join(local_root, f), 'rb') as fd:
        ftp.storlines(f'STOR {f}', fd)
for f in glob.glob(os.path.join(local_root, d, '*.vcf')):
    with open(f, 'rb') as fd:
        ftp.storbinary(f'STOR {f}', fd)
print(f'{colorama.Fore.RED}/{colorama.Style.RESET_ALL} after uploading:')
ftp.dir()
ftp.quit()
