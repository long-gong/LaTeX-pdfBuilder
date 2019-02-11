#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Setup script for PDFBuilder for LaTeX"""
from __future__ import print_function
from distutils.core import setup

name = u'LaTeXBuilder'
version = u'0.01'

setup(name=name,
      version=version,
      description='Python Tool to Building PDF for LaTeX',
      author='Long Gong',
      author_email='long.github@gmail.com',
      url='https://github.com/long-gong/LaTeX-pdfBuilder',
      packages=['pdf_builders'],
      scripts=['build.py']
      )

