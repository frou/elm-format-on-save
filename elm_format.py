import sys
import re
import sublime
import sublime_plugin
import subprocess


class ElmFormat(sublime_plugin.TextCommand):

    COMMAND_LINE = ["elm-format", "--stdin", "--yes"]
    TXT_ENCODING = "utf-8"

    # Overrides --------------------------------------------------

    def run(self, edit):
        region = sublime.Region(0, self.view.size())
        content = self.view.substr(region)

        stdout, stderr = subprocess.Popen(
            self.COMMAND_LINE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=self.platform_startupinfo(),
        ).communicate(input=bytes(content, self.TXT_ENCODING))

        errstr = stderr.strip().decode(self.TXT_ENCODING)
        errstr = re.sub("\x1b\\[\\d{1,2}m", "", errstr)  # Strip ANSI colour codes
        if errstr:
            print("\n\n{0}\n\n".format(errstr))  # noqa: T001
            sublime.set_timeout(
                lambda: sublime.status_message("ELM-FORMAT FAILED - SEE CONSOLE"), 100
            )
        else:
            self.view.replace(edit, region, stdout.decode(self.TXT_ENCODING))

    # ------------------------------------------------------------

    def platform_startupinfo(self):
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            # Stop a visible console window from appearing.
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            return si
        else:
            return None


class ElmFormatPreSave(sublime_plugin.ViewEventListener):

    SETTINGS_BASENAME = "elm-format-on-save.sublime-settings"
    SETTINGS_KEY_ONSAVE = "on_save"
    SETTINGS_KEY_INCLUDING = "including"
    SETTINGS_KEY_EXCLUDING = "excluding"

    # Overrides --------------------------------------------------

    @classmethod
    def is_applicable(cls, settings):
        return settings.get("syntax") == "Packages/ElmFeather/Elm.tmLanguage"

    def on_pre_save(self):
        try:
            if self.should_format(self.view.file_name()):
                self.view.run_command("elm_format")
        except Exception as e:
            sublime.error_message(str(e))

    # ------------------------------------------------------------

    def should_format(self, path):
        settings = sublime.load_settings(self.SETTINGS_BASENAME)
        on_save = settings.get(self.SETTINGS_KEY_ONSAVE, True)

        if isinstance(on_save, bool):
            return on_save
        elif isinstance(on_save, dict):
            included = [
                fragment in path
                for fragment in on_save.get(self.SETTINGS_KEY_INCLUDING)
            ]
            excluded = [
                fragment in path
                for fragment in on_save.get(self.SETTINGS_KEY_EXCLUDING)
            ]
            return any(included) and not any(excluded)
        else:
            raise Exception(
                '"{0}" in "{1}" has an invalid value'.format(
                    self.SETTINGS_KEY_ONSAVE, self.SETTINGS_BASENAME
                )
            )
