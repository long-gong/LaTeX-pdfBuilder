#!/usr/bin/env python
from __future__ import print_function
from pdf_builders.basicBuilder import BasicBuilder
from pdf_builders.traditionalBuilder import TraditionalBuilder
from pdf_builders.edasBuilder import EdasBuilder
from pdf_builders.pdfBuilder import check_output
import argparse
import os
from subprocess import CalledProcessError
from six import string_types, reraise


def run(pdf_builder, cur_working_dir=os.getcwd()):
    """

    :param pdf_builder:
    :param cwd:
    :return:
    """
    if pdf_builder is None:
        return
    print(cur_working_dir)
    for cmd in pdf_builder.commands():
        try:
            if isinstance(cmd, tuple):
                print(cmd[1])
                print(check_output(cmd[0], cwd=cur_working_dir))
            elif isinstance(cmd, string_types):
                print(cmd)
        except CalledProcessError as e:
            print(e.output)
            print(e.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(u'--texpath', type=str, default=u'', help=u'Path used when invoking tex & friends')
    parser.add_argument(u'--tex_root', type=str, default=os.getcwd(), help=u'Path to LaTeX root file')
    parser.add_argument(u'--output_directory', type=str, default=None, help=u'Output directory')
    parser.add_argument(u'--aux_directory', type=str, default=None, help=u'Aux directory')
    parser.add_argument(u'--jobname', type=str, default=u'LaTeX', help=u'Job name')
    parser.add_argument(u'--builder', type=str, default='traditional', help=u'Which builder to use')
    parser.add_argument(u'--builder_path', type=str, default=u'', help=u'Path to builder')
    group = parser.add_argument_group('builder_settings')
    group.add_argument(u'--display_log', action="store_true", default=True, help=u'Whether to display log')
    group.add_argument(u'--display_bad_boxes', action='store_true', default=False, help=u'Whether to display bad boxes')
    group.add_argument(u'--open_pdf_on_build', action=u'store_true', default=True, help=u'Whether to open PDF after '
                                                                                        u'build')
    args = parser.parse_args()

    builder_settings = {
        'builder_path': args.builder_path,
        'display_log': args.display_log,
        'display_bad_boxes': args.display_bad_boxes,
        'open_pdf_on_build': args.open_pdf_on_build
    }

    cur_working_dir = os.path.normpath(os.path.abspath(os.path.dirname(args.tex_root)))

    builder = None
    if args.builder == 'traditional':
        builder = TraditionalBuilder(args.tex_root, None, u'pdftex', None, args.aux_directory,
                                     args.aux_directory, args.jobname, None, builder_settings, {})
    elif args.builder == 'basic':
        builder = BasicBuilder(args.tex_root, None, u'pdftex', None, args.aux_directory,
                                     args.aux_directory, args.jobname, None, builder_settings, {})
    elif args.builder == 'edas':
        builder = EdasBuilder(args.tex_root, None, u'latex', None, args.aux_directory,
                                     args.aux_directory, args.jobname, None, builder_settings, {})
    else:
        print('Unknown builder: {}'.format(args.builder))
        parser.print_usage()
        exit(1)

    run(builder, cur_working_dir)


