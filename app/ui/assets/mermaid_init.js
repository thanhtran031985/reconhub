// Tự động khởi tạo và render Mermaid diagrams khi Dash cập nhật DOM
(function () {
    function initMermaid() {
        if (window.mermaid) {
            window.mermaid.initialize({
                startOnLoad: false,
                theme: "default",
                securityLevel: "loose",
            });
            renderMermaidElements();
        }
    }

    function renderMermaidElements() {
        if (!window.mermaid) return;
        var unrendered = document.querySelectorAll('.mermaid:not([data-processed="true"])');
        if (unrendered.length > 0) {
            try {
                window.mermaid.run({ nodes: unrendered }).catch(function (err) {
                    console.debug("Mermaid run caught:", err);
                });
            } catch (e) {
                console.debug("Mermaid run exception:", e);
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initMermaid);
    } else {
        initMermaid();
    }

    // Quan sát thay đổi DOM khi Dash chuyển tab
    var observer = new MutationObserver(function () {
        renderMermaidElements();
    });

    observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
})();

