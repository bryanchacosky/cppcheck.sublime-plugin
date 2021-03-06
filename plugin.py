import os
import re
import sublime
import sublime_plugin
import subprocess

class RewriteCommand(sublime_plugin.TextCommand):
    def run(self, edit, string):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, string)
        self.view.set_read_only(True)

class CppcheckCommand(sublime_plugin.WindowCommand):
    def run(self, rootsources):
        try:
            ### run_cppcheck

            rootsources = [p for p in rootsources if re.match(r'.+\.(h|cpp)$', p, re.I)]
            settings    = sublime.load_settings('settings.sublime-settings').get('cppcheck', {})
            cmd         = [settings.get('path')] + settings.get('args', []) + rootsources
            cppcheck    = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)

            ### generate_reports

            reports = []
            for string in cppcheck.splitlines():
                rmatch = re.match(r'^\[(.+)\:(.+)]:\s+\((.+)\)\s+(.+)', string)
                if not rmatch: continue # ignore informational output
                if not settings.get('show-included-errors', True):
                    if not rmatch.group(1) in rootsources:
                        continue # ignore non-root sources
                reports.append({\
                    'filepath': rmatch.group(1),\
                    'line':     rmatch.group(2),\
                    'severity': rmatch.group(3),\
                    'message':  rmatch.group(4) })

            ### reports_to_string

            def key_report_filepath(k):
                try:    return rootsources.index(k)
                except: return len(rootsources)

            def key_report_severity(k):
                severity_order = ['error', 'warning', 'style', 'performance', 'portability', 'information']
                return severity_order.index(k)

            def key_report(k):
                return (\
                    key_report_filepath(k['filepath']),\
                    key_report_severity(k['severity']),\
                    k['line'],\
                    k['message'])

            def pstring_severity(s):
                if s == 'performance': return 'PF'
                if s == 'portability': return 'PT'
                return s.upper()[0]

            def pstring_filepath(path):
                prefix = os.path.commonprefix([os.path.dirname(r['filepath']) for r in reports])
                rmatch = re.match(r'^%s\/(.+)' % re.escape(prefix), path)
                if not rmatch: return path
                return rmatch.group(1)

            pstring = ''
            if reports:
                for r in sorted(reports, key=key_report):
                    pstring += '%s/%s(%s): %s\n' % (
                        pstring_severity(r['severity']),
                        pstring_filepath(r['filepath']),
                        r['line'],
                        r['message'])
                pstring  = pstring.strip()
                pstring += '\n\n'
            pstring += 'Found %i reports.' % len(reports)
            pstring += '\n'

            ### print_report

            def get_or_create_view(window, name):
                for view in window.views():
                    if view.name() == name:
                        return view
                view = window.new_file()
                view.set_name(name)
                return view
            
            rname = 'Cppcheck'
            rview = get_or_create_view(self.window, rname)
            rview.run_command('rewrite', {'string': pstring})
            rview.set_syntax_file('Packages/cppcheck/syntax.tmLanguage')
            rview.set_scratch(True)
            self.window.focus_view(rview)

        except Exception as e:
            sublime.error_message(str(e))

class CppcheckActiveCommand(sublime_plugin.WindowCommand):
    def run(self):
        rootsources = [self.window.active_view().file_name()]
        self.window.run_command('cppcheck', {'rootsources':rootsources})

class CppcheckOpenCommand(sublime_plugin.WindowCommand):
    def run(self):
        rootsources = [v.file_name() for v in self.window.views()]
        self.window.run_command('cppcheck', {'rootsources':rootsources})
