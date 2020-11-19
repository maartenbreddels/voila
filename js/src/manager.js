/***************************************************************************
* Copyright (c) 2018, Voilà contributors                                   *
* Copyright (c) 2018, QuantStack                                           *
*                                                                          *
* Distributed under the terms of the BSD 3-Clause License.                 *
*                                                                          *
* The full license is in the file LICENSE, distributed with this software. *
****************************************************************************/

import { WidgetManager as JupyterLabManager } from '@jupyter-widgets/jupyterlab-manager';
import { WidgetRenderer } from '@jupyter-widgets/jupyterlab-manager';
import { output } from '@jupyter-widgets/jupyterlab-manager';

import * as base from '@jupyter-widgets/base';
import * as controls from '@jupyter-widgets/controls';

import * as Application from '@jupyterlab/application';
import * as AppUtils from '@jupyterlab/apputils';
import * as CoreUtils from '@jupyterlab/coreutils';
import * as DocRegistry from '@jupyterlab/docregistry';
import * as OutputArea from '@jupyterlab/outputarea';

import * as PhosphorWidget from '@phosphor/widgets';
import * as PhosphorSignaling from '@phosphor/signaling';
import * as PhosphorVirtualdom from '@phosphor/virtualdom';
import * as PhosphorAlgorithm from '@phosphor/algorithm';
import * as PhosphorCommands from '@phosphor/commands';
import * as PhosphorDomutils from '@phosphor/domutils';

import { MessageLoop } from '@phosphor/messaging';

import { requireLoader } from './loader';
import { batchRateMap } from './utils';
import { uuid } from '@jupyter-widgets/base';

if (typeof window !== "undefined" && typeof window.define !== "undefined") {
    window.define("@jupyter-widgets/base", base);
    window.define("@jupyter-widgets/controls", controls);
    window.define("@jupyter-widgets/output", output);

    window.define("@jupyterlab/application", Application);
    window.define("@jupyterlab/apputils", AppUtils);
    window.define("@jupyterlab/coreutils", CoreUtils);
    window.define("@jupyterlab/docregistry", DocRegistry);
    window.define("@jupyterlab/outputarea", OutputArea);

    window.define("@phosphor/widgets", PhosphorWidget);
    window.define("@phosphor/signaling", PhosphorSignaling);
    window.define("@phosphor/virtualdom", PhosphorVirtualdom);
    window.define("@phosphor/algorithm", PhosphorAlgorithm);
    window.define("@phosphor/commands", PhosphorCommands);
    window.define("@phosphor/domutils", PhosphorDomutils);
}

const WIDGET_MIMETYPE = 'application/vnd.jupyter.widget-view+json';

export class WidgetManager extends JupyterLabManager {

    constructor(context, rendermime, settings) {
        super(context, rendermime, settings);
        rendermime.addFactory({
            safe: false,
            mimeTypes: [WIDGET_MIMETYPE],
            createRenderer: options => new WidgetRenderer(options, this)
        }, 1);
        this._registerWidgets();
        this.loader = requireLoader;
    }

    async build_widgets() {
        const models = await this._build_models();
        const tags = document.body.querySelectorAll('script[type="application/vnd.jupyter.widget-view+json"]');
        for (let i=0; i!=tags.length; ++i) {
            try {
                const viewtag = tags[i];
                const widgetViewObject = JSON.parse(viewtag.innerHTML);
                const { model_id } = widgetViewObject;
                const model = models[model_id];
                const widgetel = document.createElement('div');
                viewtag.parentElement.insertBefore(widgetel, viewtag);
                const view = await this.display_model(undefined, model, { el : widgetel });
            } catch (error) {
               // Each widget view tag rendering is wrapped with a try-catch statement.
               //
               // This fixes issues with widget models that are explicitely "closed"
               // but are still referred to in a previous cell output.
               // Without the try-catch statement, this error interupts the loop and
               // prevents the rendering of further cells.
               //
               // This workaround may not be necessary anymore with templates that make use
               // of progressive rendering.
            }
        }
    }

    display_view(msg, view, options) {
        if (options.el) {
            PhosphorWidget.Widget.attach(view.pWidget, options.el);
        }
        if (view.el) {
            view.el.setAttribute('data-voila-jupyter-widget', '');
            view.el.addEventListener('jupyterWidgetResize', function(e) {
                MessageLoop.postMessage(view.pWidget, PhosphorWidget.Widget.ResizeMessage.UnknownSize);
            });
        }
        return view.pWidget;
    }

    async loadClass(className, moduleName, moduleVersion) {
        if (
            moduleName === '@jupyter-widgets/base' ||
            moduleName === '@jupyter-widgets/controls' ||
            moduleName === '@jupyter-widgets/output'
        ) {
            return super.loadClass(className, moduleName, moduleVersion);
        }
        else {
            // TODO: code duplicate from HTMLWidgetManager, consider a refactor
            return this.loader(moduleName, moduleVersion).then((module) => {
                if (module[className]) {
                    return module[className];
                }
                else {
                    return Promise.reject("Class " + className + " not found in module " + moduleName + "@" + moduleVersion);
                }
            })
        }
    }

    restoreWidgets(notebook) {
    }

    _registerWidgets() {
        this.register({
            name: '@jupyter-widgets/base',
            version: base.JUPYTER_WIDGETS_VERSION,
            exports: base
        });
        this.register({
            name: '@jupyter-widgets/controls',
            version: controls.JUPYTER_CONTROLS_VERSION,
            exports: controls
        });
        this.register({
            name: '@jupyter-widgets/output',
            version: output.OUTPUT_WIDGET_VERSION,
            exports: output
        });
    }

    async _build_models() {
        const models = {};
        const t0 = Date.now();
        this.comm_target_name_control = 'jupyter.widget.control';
        const comm_id = uuid();
        const comm = await this._create_comm(this.comm_target_name_control, comm_id, {'widgets': null});
        await new Promise((resolve) => {
            comm.on_msg((msg) => {
                resolve(msg)
            });
        })
        const t1 = Date.now();
        console.log('Getting jupyter-widget models took ', t1 - t0, ' seconds')
        return models;
    }
}
