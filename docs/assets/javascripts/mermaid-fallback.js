(function () {
  const MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

  const renderMermaidCodeBlocks = async () => {
    const blocks = Array.from(
      document.querySelectorAll("pre.mermaid, pre > code.language-mermaid")
    ).filter((block) => !block.dataset.mermaidFallbackRendered);

    if (blocks.length === 0) {
      return;
    }

    const { default: mermaid } = await import(MERMAID_URL);
    mermaid.initialize({ startOnLoad: false });

    const diagrams = blocks.map((block) => {
      block.dataset.mermaidFallbackRendered = "true";

      const source = block.textContent;
      const container = document.createElement("div");
      container.className = "mermaid";
      container.textContent = source;

      const target = block.tagName.toLowerCase() === "code" ? block.parentElement : block;
      target.replaceWith(container);

      return container;
    });

    await mermaid.run({ nodes: diagrams });
  };

  if (typeof document$ !== "undefined") {
    document$.subscribe(renderMermaidCodeBlocks);
  } else {
    document.addEventListener("DOMContentLoaded", renderMermaidCodeBlocks);
  }
})();
