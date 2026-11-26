/**
 * ReconHub — Trình tải lười (Lazy Loader) cho các thư viện JS/CSS nặng.
 * Chỉ tải Tabulator trên /templates và /batches; chỉ tải Mermaid khi DOM có .mermaid.
 */
(function () {
    "use strict";

    var loadedScripts = Object.create(null);
    var loadedCss = Object.create(null);

    function loadCss(url) {
        if (loadedCss[url]) return loadedCss[url];
        var existing = document.querySelector('link[rel="stylesheet"][href="' + url + '"]');
        if (existing) {
            loadedCss[url] = Promise.resolve();
            return loadedCss[url];
        }
        loadedCss[url] = new Promise(function (resolve, reject) {
            var link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = url;
            link.onload = function () { resolve(); };
            link.onerror = function (err) {
                delete loadedCss[url];
                reject(err);
            };
            document.head.appendChild(link);
        });
        return loadedCss[url];
    }

    function loadScript(url) {
        if (loadedScripts[url]) return loadedScripts[url];
        loadedScripts[url] = new Promise(function (resolve, reject) {
            var script = document.createElement("script");
            script.src = url;
            script.async = false;
            script.onload = function () { resolve(); };
            script.onerror = function (err) {
                delete loadedScripts[url];
                reject(err);
            };
            document.head.appendChild(script);
        });
        return loadedScripts[url];
    }

    var tabulatorPromise = null;
    function ensureTabulator() {
        if (typeof window.Tabulator !== "undefined") {
            return Promise.resolve();
        }
        if (tabulatorPromise) return tabulatorPromise;
        tabulatorPromise = Promise.all([
            loadCss("/assets/lazy/tabulator.min.css?v=1"),
            loadCss("/assets/lazy/tabulator_fluent.css?v=1"),
            loadScript("/assets/lazy/tabulator.min.js?v=1")
        ]).catch(function (err) {
            tabulatorPromise = null;
            throw err;
        });
        return tabulatorPromise;
    }

    var mermaidPromise = null;
    function ensureMermaid() {
        if (typeof window.mermaid !== "undefined") {
            if (typeof window.renderMermaidElements === "function") {
                window.renderMermaidElements();
            }
            return Promise.resolve();
        }
        if (mermaidPromise) return mermaidPromise;
        mermaidPromise = loadScript("/assets/lazy/mermaid.min.js?v=1")
            .then(function () {
                return loadScript("/assets/lazy/mermaid_init.js?v=1");
            })
            .then(function () {
                if (typeof window.renderMermaidElements === "function") {
                    window.renderMermaidElements();
                }
            })
            .catch(function (err) {
                mermaidPromise = null;
                throw err;
            });
        return mermaidPromise;
    }

    function scanForMermaidNodes() {
        if (document.querySelector('.mermaid:not([data-processed="true"])')) {
            ensureMermaid();
        }
    }

    window.reconLazy = {
        loadCss: loadCss,
        loadScript: loadScript,
        ensureTabulator: ensureTabulator,
        ensureMermaid: ensureMermaid
    };

    if (typeof window !== "undefined" && window.location && window.sessionStorage) {
        var pathNow = window.location.pathname || "";
        if (pathNow === "/login" || pathNow.indexOf("/logout") === 0) {
            try {
                window.sessionStorage.removeItem("tmpl-store-list");
                window.sessionStorage.removeItem("bdef-store-list");
                window.sessionStorage.removeItem("report-runs-swr-store");
            } catch (e) {}
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scanForMermaidNodes);
    } else {
        scanForMermaidNodes();
    }

    if (typeof MutationObserver !== "undefined") {
        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var added = mutations[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var node = added[j];
                    if (node && node.nodeType === 1) {
                        if (
                            (node.classList && node.classList.contains("mermaid")) ||
                            (node.querySelector && node.querySelector('.mermaid:not([data-processed="true"])'))
                        ) {
                            ensureMermaid();
                            return;
                        }
                    }
                }
            }
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
    }
})();
