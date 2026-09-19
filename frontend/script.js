const body = document.body;

// ==============================
// CONFIG
// ==============================

const API_BASE = "https://tmu-smart-assistant.onrender.com";
const API_URL = API_BASE + "/chat";
const RESOURCES_URL = API_BASE + "/resources";

// Stable per-browser session ID (enables follow-up questions)
const SESSION_ID =
    localStorage.getItem("tmu-session") ||
    (() => {
        const id = "s_" + Math.random().toString(36).slice(2, 10);
        localStorage.setItem("tmu-session", id);
        return id;
    })();


// ==============================
// DOM REFERENCES
// ==============================

const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const messages = document.getElementById("messages");

const welcome = document.getElementById("welcome");
const chatArea = document.getElementById("chatArea");

const themeToggle = document.getElementById("themeToggle");
const mobileThemeToggle = document.getElementById("mobileThemeToggle");

const themeIcon = document.getElementById("themeIcon");
const themeText = document.getElementById("themeText");

const sidebar = document.getElementById("sidebar");
const mobileMenu = document.getElementById("mobileMenu");

const newChatBtn = document.getElementById("newChatBtn");

let isSending = false;


// ==============================
// HELPERS
// ==============================

function escapeHtml(str) {

    if (str === null || str === undefined) {
        return "";
    }

    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}


// ==============================
// THEME
// ==============================

function updateThemeUI() {

    const dark = body.classList.contains("dark");

    if (dark) {
        themeIcon.textContent = "🌙";
        themeText.textContent = "Dark mode";
        mobileThemeToggle.textContent = "☀️";
    } else {
        themeIcon.textContent = "☀️";
        themeText.textContent = "Light mode";
        mobileThemeToggle.textContent = "🌙";
    }
}


function toggleTheme() {

    body.classList.toggle("dark");

    localStorage.setItem(
        "tmu-theme",
        body.classList.contains("dark") ? "dark" : "light"
    );

    updateThemeUI();
}


if (localStorage.getItem("tmu-theme") === "dark") {
    body.classList.add("dark");
}

updateThemeUI();

themeToggle.addEventListener("click", toggleTheme);
mobileThemeToggle.addEventListener("click", toggleTheme);


// ==============================
// SIDEBAR
// ==============================

mobileMenu.addEventListener("click", () => {
    sidebar.classList.toggle("open");
});


document.addEventListener("click", (event) => {

    if (
        window.innerWidth <= 700 &&
        sidebar.classList.contains("open") &&
        !sidebar.contains(event.target) &&
        !mobileMenu.contains(event.target)
    ) {
        sidebar.classList.remove("open");
    }
});


// ==============================
// SEND MESSAGE
// ==============================

async function sendMessage() {

    const text = messageInput.value.trim();

    if (!text || isSending) {
        return;
    }

    isSending = true;

    sendBtn.disabled = true;
    sendBtn.style.opacity = "0.5";

    welcome.style.display = "none";

    addMessage(text, "user");

    messageInput.value = "";
    autoResize();

    const loadingMessage = addLoadingMessage();

    try {

        const response = await fetch(
            API_URL,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    session_id: SESSION_ID
                })
            }
        );

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        loadingMessage.remove();

        if (data.answer) {
            addMessage(data.answer, "bot", data.sources || []);
        } else {
            addMessage("Sorry, I couldn't generate an answer.", "bot");
        }

    } catch (error) {

        console.error("Chat error:", error);

        loadingMessage.remove();

        addMessage(
            "Sorry, I couldn't connect to the TMU assistant server. Please make sure the FastAPI server is running.",
            "bot"
        );
    }

    isSending = false;
    sendBtn.disabled = false;
    sendBtn.style.opacity = "1";

    messageInput.focus();
}


// ==============================
// ADD MESSAGE
// ==============================

function addMessage(text, sender, sources = []) {

    const message = document.createElement("div");
    message.className = `message ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = sender === "user" ? "You" : "T";

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;

    message.appendChild(avatar);
    message.appendChild(content);

    // Sources go INSIDE content so they stack below the text
    if (
        sender === "bot" &&
        Array.isArray(sources) &&
        sources.length > 0
    ) {
        addSources(content, sources);
    }

    messages.appendChild(message);
    scrollToBottom();

    return message;
}


// ==============================
// ADD SOURCE BOX
// ==============================

function addSources(parent, sources) {

    const sourceBox = document.createElement("div");
    sourceBox.className = "source-box";

    const sourceLabel = document.createElement("div");
    sourceLabel.className = "source-label";
    sourceLabel.textContent = "Official TMU Sources";
    sourceBox.appendChild(sourceLabel);

    let displayIndex = 0;

    sources.forEach((source) => {

        if (!isValidTMUSource(source)) {
            return;
        }

        displayIndex += 1;

        const isPdf = source.toLowerCase().includes(".pdf");

        const sourceItem = document.createElement("div");
        sourceItem.className = "source-item";

        const sourceNumber = document.createElement("span");
        sourceNumber.className = "source-number";
        sourceNumber.textContent = `${displayIndex}.`;

        const sourceIcon = document.createElement("span");
        sourceIcon.className = "source-icon";
        sourceIcon.textContent = isPdf ? "📎" : "🔗";

        const sourceLink = document.createElement("a");
        sourceLink.className = "source-link";
        sourceLink.href = source;
        sourceLink.target = "_blank";
        sourceLink.rel = "noopener noreferrer";
        sourceLink.textContent = getSourceName(source);

        sourceItem.appendChild(sourceNumber);
        sourceItem.appendChild(sourceIcon);
        sourceItem.appendChild(sourceLink);

        sourceBox.appendChild(sourceItem);
    });

    if (displayIndex > 0) {
        parent.appendChild(sourceBox);
    }
}


// ==============================
// SOURCE SECURITY
// ==============================

function isValidTMUSource(url) {

    try {

        const parsed = new URL(url);

        return (
            parsed.protocol === "https:" &&
            (
                parsed.hostname === "www.tmu.ac.in" ||
                parsed.hostname === "tmu.ac.in"
            )
        );

    } catch {
        return false;
    }
}


// ==============================
// SOURCE NAME
// ==============================

function getSourceName(url) {

    try {

        const parsed = new URL(url);
        const path = parsed.pathname.replace(/^\/|\/$/g, "");

        if (!path) {
            return "TMU Official Website";
        }

        const parts = path.split("/");
        let lastPart = parts[parts.length - 1];

        const isPdf = lastPart.toLowerCase().endsWith(".pdf");

        if (isPdf) {
            lastPart = lastPart.slice(0, -4);
        }

        let name = lastPart
            .replace(/[-_]+/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .replace(/\b\w/g, l => l.toUpperCase());

        if (!name) {
            name = isPdf ? "TMU PDF Document" : "TMU Page";
        }

        const names = {
            "exam overview": "TMU Examination Overview",
            "exam ordinance": "TMU Examination Ordinance",
            "cbcs circulars": "TMU CBCS Circulars",
            "notice list": "TMU Notice Board",
            "scholarship": "TMU Scholarships",
            "policies sops": "TMU Policies & SOPs"
        };

        const lowerName = name.toLowerCase();

        if (names[lowerName]) {
            return names[lowerName];
        }

        if (isPdf) {
            return "PDF · " + name;
        }

        return name;

    } catch {
        return "TMU Official Website";
    }
}


// ==============================
// LOADING MESSAGE
// ==============================

function addLoadingMessage() {

    const message = document.createElement("div");
    message.className = "message bot";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "T";

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = "Thinking...";

    message.appendChild(avatar);
    message.appendChild(content);

    messages.appendChild(message);
    scrollToBottom();

    return message;
}


// ==============================
// SCROLL
// ==============================

function scrollToBottom() {

    if (chatArea) {
        chatArea.scrollTop = chatArea.scrollHeight;
    }
}


// ==============================
// TEXTAREA
// ==============================

function autoResize() {

    messageInput.style.height = "auto";
    messageInput.style.height =
        Math.min(messageInput.scrollHeight, 150) + "px";
}


messageInput.addEventListener("input", autoResize);


// ==============================
// ENTER TO SEND
// ==============================

messageInput.addEventListener("keydown", (event) => {

    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});


sendBtn.addEventListener("click", sendMessage);


// ==============================
// QUICK QUESTIONS
// ==============================

document
    .querySelectorAll("[data-question]")
    .forEach((button) => {

        button.addEventListener("click", () => {

            const question = button.dataset.question;

            messageInput.value = question;
            autoResize();
            sendMessage();

            sidebar.classList.remove("open");
        });
    });


// ==============================
// NEW CHAT
// ==============================

newChatBtn.addEventListener("click", () => {

    messages.innerHTML = "";
    welcome.style.display = "block";
    messageInput.value = "";

    autoResize();
    messageInput.focus();

    sidebar.classList.remove("open");
});


autoResize();


// ==============================
// RESOURCES + ABOUT (modal wrapper)
// ==============================

function createInfoModal(title, content) {

    const existing = document.getElementById("infoModal");

    if (existing) {
        existing.remove();
    }

    const overlay = document.createElement("div");
    overlay.id = "infoModal";
    overlay.className = "info-modal-overlay";

    const modal = document.createElement("div");
    modal.className = "info-modal";

    const header = document.createElement("div");
    header.className = "info-modal-header";

    const heading = document.createElement("h2");
    heading.textContent = title;

    const close = document.createElement("button");
    close.className = "info-modal-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close");

    close.addEventListener("click", () => overlay.remove());

    header.appendChild(heading);
    header.appendChild(close);

    const body = document.createElement("div");
    body.className = "info-modal-body";
    body.innerHTML = content;

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            overlay.remove();
        }
    });

    document.body.appendChild(overlay);

    return overlay;
}


function getModalBody() {
    return document.querySelector("#infoModal .info-modal-body");
}


// ==============================
// RESOURCES (dynamic — loads all PDFs from /resources)
// ==============================

async function openResources() {

    createInfoModal(
        "TMU Resources",
        `
        <p class="modal-description">Loading official resources…</p>
        <div class="loading-spinner"></div>
        `
    );

    try {

        const resp = await fetch(RESOURCES_URL);

        if (!resp.ok) {
            throw new Error(`Server returned ${resp.status}`);
        }

        const data = await resp.json();

        const modalBody = getModalBody();

        if (!modalBody) {
            return;
        }

        let html = `
            <p class="modal-description">
                Official TMU pages and downloadable documents
                (${data.total_pdfs || 0} PDFs found).
            </p>
        `;

        // ---- Official pages ----
        if (data.pages && data.pages.length > 0) {

            html += `
                <div class="resource-section">
                    <h4>Official Pages</h4>
                    <div class="resource-grid">
            `;

            data.pages.forEach((p) => {
                html += `
                    <a href="${escapeHtml(p.url)}"
                       target="_blank"
                       rel="noopener noreferrer"
                       class="resource-card">
                        <span class="resource-icon">🔗</span>
                        <span>
                            <strong>${escapeHtml(p.name)}</strong>
                            <small>${escapeHtml(p.url)}</small>
                        </span>
                    </a>
                `;
            });

            html += `</div></div>`;
        }

        // ---- Downloadable PDFs ----
        if (data.pdf_groups && data.pdf_groups.length > 0) {

            html += `
                <div class="resource-section">
                    <h4>Downloadable Documents</h4>
            `;

            data.pdf_groups.forEach((g) => {

                html += `
                    <div class="pdf-group">
                        <div class="pdf-group-title">
                            ${escapeHtml(g.category)}
                            <span class="pdf-count">${g.items.length}</span>
                        </div>
                        <div class="pdf-list">
                `;

                g.items.forEach((item) => {
                    html += `
                        <a href="${escapeHtml(item.url)}"
                           target="_blank"
                           rel="noopener noreferrer"
                           class="pdf-item">
                            <span class="pdf-icon">📎</span>
                            <span class="pdf-name">${escapeHtml(item.name)}</span>
                        </a>
                    `;
                });

                html += `</div></div>`;
            });

            html += `</div>`;
        }

        if (
            (!data.pages || data.pages.length === 0) &&
            (!data.pdf_groups || data.pdf_groups.length === 0)
        ) {
            html += `<p class="modal-description">No resources available yet.</p>`;
        }

        modalBody.innerHTML = html;

    } catch (error) {

        console.error("Resources error:", error);

        const modalBody = getModalBody();

        if (modalBody) {
            modalBody.innerHTML = `
                <p class="modal-description">
                    Unable to load resources right now.
                    Please try again in a moment.
                </p>
            `;
        }
    }
}


// ==============================
// ABOUT
// ==============================

function openAbout() {

    createInfoModal(
        "About TMU AI Assistant",

        `
        <div class="about-content">

            <div class="about-logo">🤖</div>

            <h3>TMU AI Student Assistant</h3>

            <p>
                An AI-powered student information assistant
                designed to help students find information
                from publicly available official TMU sources.
            </p>

            <div class="about-section">
                <strong>How it works</strong>
                <p>
                    The assistant searches official TMU
                    webpages and documents, retrieves relevant
                    information, and uses AI to provide a
                    concise answer.
                </p>
            </div>

            <div class="about-section">
                <strong>Information sources</strong>
                <p>
                    Information is retrieved from official
                    TMU webpages, notices, circulars,
                    policies, SOPs and other public documents.
                </p>
            </div>

            <div class="about-section">
                <strong>Privacy</strong>
                <p>
                    This assistant does not access private
                    student ERP information such as personal
                    attendance, marks, results or fee records.
                </p>
            </div>

            <div class="about-section">
                <strong>Project Team</strong>
                <div class="team-grid">

                    <div class="team-member">
                        <div class="team-avatar">AY</div>
                        <div class="team-info">
                            <strong>Anuj Yadav</strong>
                            <small>Team Leader · BCA 5th Sem</small>
                        </div>
                    </div>

                    <div class="team-member">
                        <div class="team-avatar">AR</div>
                        <div class="team-info">
                            <strong>Ankit Ram</strong>
                            <small>BCA 5th Sem</small>
                        </div>
                    </div>

                    <div class="team-member">
                        <div class="team-avatar">AG</div>
                        <div class="team-info">
                            <strong>Abhigay Kr Gupta</strong>
                            <small>BCA 5th Sem</small>
                        </div>
                    </div>

                    <div class="team-member">
                        <div class="team-avatar">AS</div>
                        <div class="team-info">
                            <strong>Abhishek Singh</strong>
                            <small>BCA 5th Sem</small>
                        </div>
                    </div>

                </div>
            </div>

            <div class="about-section">
                <strong>Project Instructor</strong>
                <p>Ms. Anvesha Sisodiya</p>
            </div>

            <div class="about-warning">
                Always verify important or time-sensitive
                information using the official TMU source
                provided with the answer.
            </div>

        </div>
        `
    );
}


// ==============================
// FIND SIDEBAR BUTTONS
// ==============================

function setupInfoButtons() {

    const sidebarItems = sidebar.querySelectorAll(
        "a, button, .nav-item, .sidebar-item, .side-item"
    );

    sidebarItems.forEach((item) => {

        const text = item.textContent.trim().toLowerCase();

        if (text.includes("resources")) {

            item.addEventListener("click", (event) => {
                event.preventDefault();
                openResources();
                sidebar.classList.remove("open");
            });
        }

        if (text.includes("about")) {

            item.addEventListener("click", (event) => {
                event.preventDefault();
                openAbout();
                sidebar.classList.remove("open");
            });
        }
    });
}


setupInfoButtons();


// ==============================
// ESCAPE CLOSES MODAL
// ==============================

document.addEventListener("keydown", (event) => {

    if (event.key === "Escape") {

        const modal = document.getElementById("infoModal");

        if (modal) {
            modal.remove();
        }
    }
});