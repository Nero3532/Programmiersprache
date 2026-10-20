# -*- coding: utf-8 -*-
"""
Deutsch – Aufruf als Modul: py -m deutsch [Optionen] [datei.deu]

Verhält sich wie main.py (gleiche Optionen und Exitcodes). Das Modul 'main' liegt
im Repo-Checkout im Wurzelordner und nach 'pip install' als Top-Level-Modul im
site-packages-Ordner; in beiden Fällen ist es importierbar.
"""
import main

if __name__ == '__main__':
    main.main()
