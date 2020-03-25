import sublime
import sublime_plugin

import re
import subprocess
import sys


class PreSaveFormat(sublime_plugin.TextCommand):

    TXT_ENCODING = "utf-8"

    # Overrides --------------------------------------------------

    def run(self, edit, command_line, append_file_path_to_command_line, **_):
        try:
            self.run_core(edit, command_line, append_file_path_to_command_line)
        except Exception as e:
            sublime.error_message(str(e))

    # ------------------------------------------------------------

    def run_core(self, edit, command_line, append_file_path_to_command_line):
        view_region = sublime.Region(0, self.view.size())
        view_content = self.view.substr(view_region)

        if append_file_path_to_command_line:
            command_line.append(self.view.file_name())

        child_proc = subprocess.Popen(
            command_line,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=self.platform_startupinfo(),
        )
        stdout_content, stderr_content = child_proc.communicate(
            input=bytes(view_content, self.TXT_ENCODING)
        )
        stdout_content, stderr_content = (
            stdout_content.decode(self.TXT_ENCODING),
            self.postprocess_stderr(stderr_content.decode(self.TXT_ENCODING)),
        )

        if child_proc.returncode != 0:
            print("\n\n{0}\n\n".format(stderr_content))  # noqa: T001
            sublime.set_timeout(
                lambda: sublime.status_message(
                    "{0} failed - see console".format(command_line[0]).upper()
                ),
                100,
            )
            return

        if not len(stdout_content):
            raise Exception(
                "{0} produced no output despite exiting successfully".format(
                    command_line[0]
                )
            )
        self.view.replace(edit, view_region, stdout_content)

    def postprocess_stderr(self, s):
        # Remove ANSI colour codes
        s = re.sub("\x1b\\[\\d{1,2}m", "", s)
        return s.strip()

    def platform_startupinfo(self):
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            # Stop a visible console window from appearing.
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            return si
        else:
            return None


class PreSaveListener(sublime_plugin.ViewEventListener):

    # @todo #0 Use `PreSaveFormat.__class__.__name__` as PKG_SETTINGS_BASENAME
    PKG_SETTINGS_BASENAME = "{0}.sublime-settings".format("ElmFormatPreSave")
    PKG_SETTINGS = sublime.load_settings(PKG_SETTINGS_BASENAME)
    PKG_SETTINGS_KEY_ENABLED = "enabled"
    PKG_SETTINGS_KEY_INCLUDE = "include"
    PKG_SETTINGS_KEY_EXCLUDE = "exclude"

    # Overrides --------------------------------------------------

    @classmethod
    def is_applicable(cls, settings):
        syntax_path = cls.get_syntax_path(settings)
        lang_settings = cls.PKG_SETTINGS.get(syntax_path)
        return lang_settings is not None

    def on_pre_save(self):
        try:
            syntax_path = self.get_syntax_path(self.view)
            lang_settings = self.PKG_SETTINGS.get(syntax_path)
            if self.should_format(self.view.file_name(), lang_settings):
                self.view.run_command("pre_save_format", lang_settings)
        except Exception as e:
            sublime.error_message(str(e))

    # ------------------------------------------------------------

    @classmethod
    def get_syntax_path(cls, settings):
        if isinstance(settings, sublime.View):
            settings = settings.settings()
        return settings.get("syntax")

    def should_format(self, path, lang_settings):
        if not lang_settings.get(self.PKG_SETTINGS_KEY_ENABLED, True):
            return False

        # @todo #0 Use Python stdlib "glob" rather than basic substring matching.
        #  And add a comment in the default settings file explaining the logic.
        include_hits = [
            fragment in path
            for fragment in lang_settings.get(self.PKG_SETTINGS_KEY_INCLUDE)
        ]
        exclude_hits = [
            fragment in path
            for fragment in lang_settings.get(self.PKG_SETTINGS_KEY_EXCLUDE)
        ]
        return any(include_hits) and not any(exclude_hits)
