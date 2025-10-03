(function () {
  function onReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function createFragment(html) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    return template.content;
  }

  function swapContent(target, html, swap) {
    if (!target) {
      return;
    }

    if (swap === "outerHTML") {
      if (html.trim() === "") {
        target.outerHTML = html;
        return;
      }
      const fragment = createFragment(html);
      const firstElement = fragment.firstElementChild;
      if (firstElement) {
        target.replaceWith(firstElement);
      } else {
        target.outerHTML = html;
      }
      return;
    }

    target.innerHTML = html;
  }

  function resolveTarget(element, selector) {
    if (!selector) {
      return null;
    }

    if (selector.startsWith("closest ")) {
      const actual = selector.replace("closest ", "").trim();
      if (!actual) {
        return null;
      }
      return element.closest(actual);
    }

    return document.querySelector(selector);
  }

  function buildHeaders(authHeader, extra) {
    const headers = {
      "HX-Request": "true",
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    };

    if (authHeader) {
      headers.Authorization = authHeader;
    }

    return Object.assign(headers, extra || {});
  }

  async function fetchFragment(url, options) {
    const response = await fetch(url, Object.assign({ credentials: "include" }, options));
    const text = await response.text();
    return { response, text };
  }

  function dispatchSuccessEvent(element) {
    const eventName = element.getAttribute("data-success-event");
    if (!eventName) {
      return;
    }

    if (window.htmx && typeof window.htmx.trigger === "function") {
      window.htmx.trigger(document.body, eventName);
      return;
    }

    document.body.dispatchEvent(new CustomEvent(eventName, { bubbles: true }));
  }

  function handleSuccess(formLike) {
    if (formLike instanceof HTMLFormElement) {
      if (formLike.getAttribute("data-reset-on-success") === "true") {
        formLike.reset();
      }
    }
    dispatchSuccessEvent(formLike);
  }

  async function refreshLinks(authHeader) {
    const countAnchor = document.getElementById("short-link-count");
    if (countAnchor) {
      try {
        const { response, text } = await fetchFragment("/admin/links/count", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(countAnchor, text, "outerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh short link count", error);
      }
    }

    const tableContainer = document.getElementById("links-table");
    if (tableContainer) {
      try {
        const { response, text } = await fetchFragment("/admin/links/table", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(tableContainer, text, "innerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh short link table", error);
      }
    }
  }

  async function refreshSubdomains(authHeader) {
    const countAnchor = document.getElementById("subdomain-count");
    if (countAnchor) {
      try {
        const { response, text } = await fetchFragment("/admin/subdomains/count", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(countAnchor, text, "outerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh subdomain count", error);
      }
    }

    const tableContainer = document.getElementById("subdomains-table");
    if (tableContainer) {
      try {
        const { response, text } = await fetchFragment("/admin/subdomains/table", {
          method: "GET",
          headers: buildHeaders(authHeader),
        });
        if (response.ok) {
          swapContent(tableContainer, text, "innerHTML");
        }
      } catch (error) {
        console.error("Failed to refresh subdomain table", error);
      }
    }
  }

  onReady(() => {
    const authHeader = document.body.dataset.authHeader || "";
    const useFallback = typeof window.htmx === "undefined";

    if (!useFallback) {
      document.body.addEventListener("htmx:afterRequest", (event) => {
        const detail = event.detail || {};
        const { successful, xhr } = detail;
        const status = xhr && typeof xhr.status === "number" ? xhr.status : 0;
        const isSuccessful =
          typeof successful === "boolean"
            ? successful
            : status >= 200 && status < 400;
        if (!isSuccessful) {
          return;
        }
        const source = event.target;
        if (!(source instanceof HTMLElement)) {
          return;
        }

        const target = source.closest("[data-success-event]") || source;
        if (target instanceof HTMLElement) {
          handleSuccess(target);
        }
      });
      return;
    }

    console.warn("htmx 未加载，使用回退逻辑处理管理后台交互。\n建议检查 CDN 是否可访问。");

    const refreshLinksHandler = () => refreshLinks(authHeader);
    const refreshSubdomainsHandler = () => refreshSubdomains(authHeader);

    document.body.addEventListener("refresh-links", refreshLinksHandler);
    document.body.addEventListener("refresh-subdomains", refreshSubdomainsHandler);

    refreshLinksHandler();
    refreshSubdomainsHandler();

    document.body.addEventListener("submit", async (event) => {
      const form = event.target instanceof HTMLFormElement
        ? event.target
        : event.target.closest("form");
      if (!form) {
        return;
      }

      const targetUrl = form.getAttribute("hx-post") || form.getAttribute("hx-put");
      if (!targetUrl) {
        return;
      }

      event.preventDefault();

      const method = form.getAttribute("hx-post") ? "POST" : "PUT";
      const targetSelector = form.getAttribute("hx-target");
      const swapStrategy = form.getAttribute("hx-swap") || "innerHTML";
      const target = resolveTarget(form, targetSelector);

      const formData = new FormData(form);
      const body = new URLSearchParams();
      formData.forEach((value, key) => {
        if (typeof value === "string") {
          body.append(key, value);
        }
      });

      try {
        const { response, text } = await fetchFragment(targetUrl, {
          method,
          headers: buildHeaders(authHeader, {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          }),
          body,
        });

        if (target) {
          swapContent(target, text, swapStrategy);
        }

        if (response.ok) {
          handleSuccess(form);
        }
      } catch (error) {
        if (target) {
          target.textContent = "请求失败，请稍后再试";
        }
        console.error("Failed to submit form", error);
      }
    });

    document.body.addEventListener("click", async (event) => {
      const trigger = event.target.closest("[hx-get], [hx-delete]");
      if (!trigger) {
        return;
      }

      const isGet = trigger.hasAttribute("hx-get");
      const isDelete = trigger.hasAttribute("hx-delete");

      if (isDelete) {
        const message = trigger.getAttribute("hx-confirm");
        if (message && !window.confirm(message)) {
          return;
        }
      }

      event.preventDefault();

      const url = trigger.getAttribute(isGet ? "hx-get" : "hx-delete");
      const targetSelector = trigger.getAttribute("hx-target");
      const swapStrategy = trigger.getAttribute("hx-swap") || "innerHTML";
      const target = resolveTarget(trigger, targetSelector);

      try {
        const { response, text } = await fetchFragment(url, {
          method: isDelete ? "DELETE" : "GET",
          headers: buildHeaders(authHeader),
        });

        if (target) {
          swapContent(target, text, swapStrategy);
        }

        if (response.ok && !isGet) {
          // 删除操作会触发刷新事件
          handleSuccess(trigger);
        }
      } catch (error) {
        if (target) {
          target.textContent = "请求失败，请稍后再试";
        }
        console.error("Failed to process request", error);
      }
    });
  });
})();
