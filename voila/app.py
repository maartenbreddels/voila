#############################################################################
# Copyright (c) 2018, Voila Contributors                                    #
# Copyright (c) 2018, QuantStack                                            #
#                                                                           #
# Distributed under the terms of the BSD 3-Clause License.                  #
#                                                                           #
# The full license is in the file LICENSE, distributed with this software.  #
#############################################################################

import gettext
import logging
import os

import jinja2

from traitlets import Unicode, Integer, Bool, Dict, List

from jupyter_server.extension.application import ExtensionApp
from jupyter_server.serverapp import ServerApp
from jupyter_server.base.handlers import FileFindHandler, path_regex
from jupyter_core.paths import jupyter_config_path, jupyter_path

from .paths import ROOT, STATIC_ROOT, collect_template_paths
from .handler import VoilaHandler
from .treehandler import VoilaTreeHandler
from .static_file_handler import WhiteListFileHandler
from ._version import __version__
from .execute import VoilaExecutor
from .exporter import VoilaExporter
from .csspreprocessor import VoilaCSSPreprocessor

_kernel_id_regex = r"(?P<kernel_id>\w+-\w+-\w+-\w+-\w+)"


def _(x):
    return x


class Voila(ExtensionApp):
    extension_name = 'voila'
    extension_url = '/voila'
    load_other_extensions = True

    version = __version__
    examples = 'jupyter voila example.ipynb'

    flags = {
        'debug': (
            {'ServerApp': {'log_level': logging.DEBUG}},
            _("Set the log level to logging.DEBUG")
        ),
        'no-browser': (
            {'Voila': {'open_browser': False}},
            _("Don't open the notebook in a browser after startup.")
        ),
        "standalone": (
            {"ServerApp": {"standalone": True}},
            _("Run the server without enabling extensions."),
        ),
    }

    description = Unicode(
        """voila [OPTIONS] NOTEBOOK_FILENAME

        This launches a stand-alone server for read-only notebooks.
        """
    )
    option_description = Unicode(
        """
        notebook_path:
            File name of the Jupyter notebook to display.
        """
    )

    autoreload = Bool(
        False,
        config=True,
        help=_(
            'Will autoreload to server and the page when a template, js file or Python code changes'
        )
    )
    static_root = Unicode(
        STATIC_ROOT,
        config=True,
        help=_(
            'Directory holding static assets (HTML, JS and CSS files).'
        )
    )
    aliases = {
        'static': 'Voila.static_root',
        'strip_sources': 'Voila.strip_sources',
        'autoreload': 'Voila.autoreload',
        'template': 'Voila.template',
        'theme': 'Voila.theme',
        'enable_nbextensions': 'Voila.enable_nbextensions',
    }
    classes = [
        VoilaExecutor,
        VoilaExporter,
        VoilaCSSPreprocessor,
        ServerApp
    ]
    template = Unicode(
        "default",
        config=True,
        allow_none=True,
        help=("template name to be used by voila."),
    )
    file_whitelist = List(
        Unicode(),
        [r".*\.(png|jpg|gif|svg)"],
        help=r"""
        List of regular expressions for controlling which static files are served.
        All files that are served should at least match 1 whitelist rule, and no blacklist rule
        Example: --Voila.file_whitelist="['.*\.(png|jpg|gif|svg)', 'public.*']"
        """,
    ).tag(config=True)

    file_blacklist = List(
        Unicode(),
        [r".*\.(ipynb|py)"],
        help=r"""
        List of regular expressions for controlling which static files are forbidden to be served.
        All files that are served should at least match 1 whitelist rule, and no blacklist rule
        Example:
        --Voila.file_whitelist="['.*']" # all files
        --Voila.file_blacklist="['private.*', '.*\.(ipynb)']" # except files in the private dir and notebook files
        """,
    ).tag(config=True)

    language_kernel_mapping = Dict(
        {},
        help="""Mapping of language name to kernel name
        Example mapping python to use xeus-python, and C++11 to use xeus-cling:
        --Voila.extension_language_mapping='{"python": "xpython", "C++11": "xcpp11"}'
        """,
    ).tag(config=True)

    extension_language_mapping = Dict(
        {},
        help="""Mapping of file extension to kernel language
        Example mapping .py files to a python language kernel, and .cpp to a C++11 language kernel:
        --Voila.extension_language_mapping='{".py": "python", ".cpp": "C++11"}'
        """,
    ).tag(config=True)

    resources = Dict(
        allow_none=True,
        help="""
        extra resources used by templates;
        example use with --template=reveal
        --Voila.resources="{'reveal': {'transition': 'fade', 'scroll': True}}"
        """,
    ).tag(config=True)

    theme = Unicode("light").tag(config=True)

    strip_sources = Bool(True, help="Strip sources from rendered html").tag(config=True)

    enable_nbextensions = Bool(
        False, config=True, help=("Set to True for Voila to load notebook extensions")
    )
    connection_dir_root = Unicode(
        config=True,
        help=_(
            'Location of temporary connection files. Defaults '
            'to system `tempfile.gettempdir()` value.'
        )
    )
    connection_dir = Unicode()

    nbconvert_template_paths = List(
        [],
        config=True,
        help=_(
            'path to nbconvert templates'
        )
    )

    template_paths = []

    static_paths = [STATIC_ROOT]

    webbrowser_open_new = Integer(2, config=True,
                                  help=_("""Specify Where to open the notebook on startup. This is the
                                  `new` argument passed to the standard library method `webbrowser.open`.
                                  The behaviour is not guaranteed, but depends on browser support. Valid
                                  values are:
                                  - 2 opens a new tab,
                                  - 1 opens a new window,
                                  - 0 opens in an existing window.
                                  See the `webbrowser.open` documentation for details.
                                  """))

    custom_display_url = Unicode(u'', config=True,
                                 help=_("""Override URL shown to users.
                                 Replace actual URL, including protocol, address, port and base URL,
                                 with the given value when displaying URL to the users. Do not change
                                 the actual connection URL. If authentication token is enabled, the
                                 token is added to the custom URL automatically.
                                 This option is intended to be used when the URL to display to the user
                                 cannot be determined reliably by the Jupyter notebook server (proxified
                                 or containerized setups for example)."""))

    config_file_paths = List(
        Unicode(),
        config=True,
        help=_(
            'Paths to search for jupyter_voila_config.(py|json)'
        )
    )

    # similar to NotebookApp, except no extra path
    @property
    def nbextensions_path(self):
        """The path to look for Javascript notebook extensions"""
        path = jupyter_path('nbextensions')
        # FIXME: remove IPython nbextensions path after a migration period
        try:
            from IPython.paths import get_ipython_dir
        except ImportError:
            pass
        else:
            path.append(os.path.join(get_ipython_dir(), 'nbextensions'))
        return path

    default_url = Unicode("/voila", config=True)

    def link_to_serverapp(self, serverapp):
        self.update_config(serverapp.config)
        super().link_to_serverapp(serverapp)

    def initialize_settings(self):
        # Ensure the server finds both serverconfig and nbconfig.
        paths = self.serverapp.config_manager.read_config_path
        for p in jupyter_config_path():
            paths.extend([os.path.join(p, "serverconfig"), os.path.join(p, "nbconfig")])
        # Keep unique paths.
        paths = list(set(paths))
        self.serverapp.config_manager.read_config_path = paths

        # Pass notebook path to settings.
        self.settings.update({"notebook_path": self.serverapp.file_to_run})

        # If we are in standalone mode, we want to restrict the allowed messages
        # to not allow arbitrary code execution.
        extensions = set(self.serverapp.jpserver_extensions)
        # voila.server_extension is the old name, but better be on the safe side, and
        # expect messy environments
        other_extensions = extensions.difference({'voila', 'voila.server_extension'})
        if not other_extensions:
            self.serverapp.log.info("Running in standalone mode, disabling execute_request")
            self.serverapp.kernel_manager.allowed_message_types = [
                'comm_open',
                'comm_close',
                'comm_msg',
                'comm_info_request',
                'kernel_info_request',
                'shutdown_request',
            ]

    def initialize_templates(self):
        if self.template:
            # common configuration options between the server extension and the application
            collect_template_paths(
                self.nbconvert_template_paths,
                self.static_paths,
                self.template_paths,
                self.template,
            )

        self.serverapp.log.debug("using template: %s", self.template)
        self.serverapp.log.debug(
            "nbconvert template paths:\n\t%s",
            "\n\t".join(self.nbconvert_template_paths),
        )
        self.serverapp.log.debug(
            "template paths:\n\t%s", "\n\t".join(self.template_paths)
        )
        self.serverapp.log.debug("static paths:\n\t%s", "\n\t".join(self.static_paths))

        jenv_opt = {"autoescape": True}
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_paths),
            extensions=["jinja2.ext.i18n"],
            **jenv_opt
        )

        nbui = gettext.translation(
            "nbui", localedir=os.path.join(ROOT, "i18n"), fallback=True
        )
        env.install_gettext_translations(nbui, newstyle=False)

        template_settings = {"voila_jinja2_env": env}
        self.settings.update(**template_settings)

    def initialize_handlers(self):
        # Serving notebook extensions
        if self.enable_nbextensions:
            # Note, this handler 'overlaps' with the "/static/voila" handler that our base
            # class adds. Since this regex is more specific, and added first, we're all good.
            self.handlers.insert(
                0,
                (
                    "static/voila/nbextensions/(.*)",
                    FileFindHandler,
                    {"path": self.nbextensions_path, "no_cache_paths": ["/"]},
                ),
            )

        self.handlers.append(
            (
                "/voila/files/(.*)",
                WhiteListFileHandler,
                {
                    "whitelist": self.file_whitelist,
                    "blacklist": self.file_blacklist,
                    "path": self.serverapp.root_dir,
                },
            )
        )

        if self.serverapp.file_to_run:
            self.handlers.append(("/voila", VoilaHandler))
            self.serverapp.file_to_run = ''
        else:
            handlers = [
                ("/voila/render" + path_regex, VoilaHandler),
                ("/voila", VoilaTreeHandler),
                ("/voila/tree" + path_regex, VoilaTreeHandler),
            ]
            self.handlers.extend(handlers)


main = Voila.launch_instance
