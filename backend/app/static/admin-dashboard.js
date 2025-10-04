(function () {
  const THEME_STORAGE_KEY = "yetla-admin-theme";
  let storedThemeValue = null;

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

  function toAbsoluteUrl(url) {
    if (!url) {
      return url;
    }

    try {
      const base = `${window.location.protocol}//${window.location.host}`;
      return new URL(url, base).toString();
    } catch (error) {
      console.warn("Failed to construct absolute URL", url, error);
      return url;
    }
  }

  async function fetchFragment(url, options) {
    const absoluteUrl = toAbsoluteUrl(url);
    const response = await fetch(
      absoluteUrl,
      Object.assign({ credentials: "include" }, options),
    );
    const text = await response.text();
    return { response, text };
  }

  async function submitWithFallback(formLike, submitter, authHeaderValue) {
    if (!(formLike instanceof HTMLFormElement)) {
      return;
    }

    if (
      !formLike.hasAttribute("hx-post") &&
      !formLike.hasAttribute("hx-put")
    ) {
      return;
    }

    if (formLike.dataset.htmxSubmitting === "true") {
      return;
    }

    const targetUrl =
      formLike.getAttribute("hx-post") || formLike.getAttribute("hx-put");
    if (!targetUrl) {
      return;
    }

    formLike.dataset.htmxSubmitting = "true";

    const method = formLike.hasAttribute("hx-post") ? "POST" : "PUT";
    const targetSelector = formLike.getAttribute("hx-target");
    const swapStrategy = formLike.getAttribute("hx-swap") || "innerHTML";
    const target = resolveTarget(formLike, targetSelector);

    const formData = new FormData(formLike);
    if (
      submitter &&
      typeof submitter.name === "string" &&
      submitter.name &&
      !formData.has(submitter.name)
    ) {
      formData.append(submitter.name, submitter.value);
    }

    const body = new URLSearchParams();
    formData.forEach((value, key) => {
      if (typeof value === "string") {
        body.append(key, value);
      }
    });

    try {
      const { response, text } = await fetchFragment(targetUrl, {
        method,
        headers: buildHeaders(authHeaderValue, {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }),
        body,
      });

      if (target) {
        swapContent(target, text, swapStrategy);
      }

      if (response.ok) {
        handleSuccess(formLike);
      }
    } catch (error) {
      if (target) {
        target.textContent = "请求失败，请稍后再试";
      }
      console.error("Failed to submit form", error);
    } finally {
      delete formLike.dataset.htmxSubmitting;
    }
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

  function highlightThemeCards(activeTheme, previewTheme) {
    const cards = document.querySelectorAll("[data-theme-option]");
    cards.forEach((card) => {
      const option = card.getAttribute("data-theme-option");
      const isActive = option === activeTheme;
      const isPreview = previewTheme && option === previewTheme;
      card.classList.toggle("is-active", Boolean(isActive));
      card.classList.toggle("is-preview", Boolean(isPreview) && !isActive);

      const applyButton = card.querySelector("[data-theme-apply]");
      if (applyButton) {
        applyButton.setAttribute("aria-pressed", isActive ? "true" : "false");
      }
    });
  }

  function setTheme(theme, { persist = false, preview = false } = {}) {
    if (!theme) {
      return;
    }

    const root = document.documentElement;
    const body = document.body;

    if (root) {
      root.setAttribute("data-theme", theme);
    }
    if (body) {
      body.setAttribute("data-theme", theme);
    }

    if (persist) {
      storedThemeValue = theme;
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, theme);
      } catch (error) {
        /* ignore storage failures */
      }
    }

    const active = storedThemeValue || theme;
    highlightThemeCards(active, preview ? theme : undefined);
  }

  function getStoredTheme() {
    if (storedThemeValue) {
      return storedThemeValue;
    }

    let saved = "aurora";
    try {
      const fromStorage = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (fromStorage) {
        saved = fromStorage;
      } else {
        const attr = document.documentElement.getAttribute("data-theme");
        if (attr) {
          saved = attr;
        }
      }
    } catch (error) {
      const attr = document.documentElement.getAttribute("data-theme");
      if (attr) {
        saved = attr;
      }
    }

    storedThemeValue = saved;
    return saved;
  }

  function restorePersistedTheme() {
    const theme = getStoredTheme();
    setTheme(theme, { persist: false });
  }

  function bindThemeGallery() {
    const cards = Array.from(
      document.querySelectorAll("[data-theme-option]"),
    );

    if (!cards.length) {
      return;
    }

    const handleApply = (event) => {
      const button = event.currentTarget;
      const theme = button.getAttribute("data-theme-apply");
      if (!theme) {
        return;
      }
      event.preventDefault();
      setTheme(theme, { persist: true });
    };

    cards.forEach((card) => {
      const theme = card.getAttribute("data-theme-option");
      const applyButton = card.querySelector("[data-theme-apply]");

      if (applyButton) {
        applyButton.addEventListener("click", handleApply);
      }

      card.addEventListener("mouseenter", () => {
        if (theme) {
          setTheme(theme, { preview: true });
        }
      });

      card.addEventListener("mouseleave", () => {
        const saved = getStoredTheme();
        setTheme(saved, { persist: false });
      });

      card.addEventListener("click", (event) => {
        if (event.target.closest("[data-theme-apply]")) {
          return;
        }
        if (theme) {
          setTheme(theme, { persist: true });
        }
      });

      card.addEventListener("focusin", () => {
        if (theme) {
          setTheme(theme, { preview: true });
        }
      });

      card.addEventListener("focusout", () => {
        const saved = getStoredTheme();
        setTheme(saved, { persist: false });
      });

      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          if (!theme) {
            return;
          }
          event.preventDefault();
          setTheme(theme, { persist: true });
        }
      });
    });

    const saved = getStoredTheme();
    highlightThemeCards(saved);
  }

  onReady(() => {
    const authHeader = document.body.dataset.authHeader || "";
    const useFallback = typeof window.htmx === "undefined";

    restorePersistedTheme();
    bindThemeGallery();

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
      const form =
        event.target instanceof HTMLFormElement
          ? event.target
          : event.target.closest("form");
      if (!form) {
        return;
      }

      if (form.dataset.htmxSubmitting === "true") {
        event.preventDefault();
        return;
      }

      if (!form.hasAttribute("hx-post") && !form.hasAttribute("hx-put")) {
        return;
      }

      event.preventDefault();

      const submitter =
        typeof event.submitter !== "undefined" && event.submitter
          ? event.submitter
          : undefined;
      await submitWithFallback(form, submitter, authHeader);
    });

    document.body.addEventListener("click", async (event) => {
      const submitter = event.target.closest(
        "button[type=submit], input[type=submit]",
      );
      if (submitter) {
        const form = submitter.form || submitter.closest("form");
        if (form) {
          if (form.dataset.htmxSubmitting === "true") {
            event.preventDefault();
            return;
          }
          if (form.hasAttribute("hx-post") || form.hasAttribute("hx-put")) {
            event.preventDefault();
            await submitWithFallback(form, submitter, authHeader);
            return;
          }
        }
      }

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
