const body = document.body;

// ==============================
// CONFIG
// ==============================

// Change this to your deployed HTTPS API later
const API_URL = "https://tmu-smart-assistant.onrender.com/chat";

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
        body.classList.contains("dark")
            ? "dark"
            : "light"
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

mobileMenu.addEventListener(
    "click",
    () => {

        sidebar.classList.toggle("open");

    }
);


document.addEventListener(
    "click",
    (event) => {

        if (
            window.innerWidth <= 700 &&
            sidebar.classList.contains("open") &&
            !sidebar.contains(event.target) &&
            !mobileMenu.contains(event.target)
        ) {

            sidebar.classList.remove("open");

        }

    }
);


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

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    message: text,
                    session_id: SESSION_ID
                })
            }
        );


        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );

        }


        const data = await response.json();


        loadingMessage.remove();


        if (data.answer) {

            addMessage(
                data.answer,
                "bot",
                data.sources || []
            );

        } else {

            addMessage(
                "Sorry, I couldn't generate an answer.",
                "bot"
            );

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

function addMessage(
    text,
    sender,
    sources = []
) {

    const message = document.createElement("div");

    message.className = `message ${sender}`;


    const avatar = document.createElement("div");

    avatar.className = "avatar";

    avatar.textContent =
        sender === "user" ? "You" : "T";


    const content = document.createElement("div");

    content.className = "message-content";

    // Safe text rendering
    content.textContent = text;


    message.appendChild(avatar);
    message.appendChild(content);


    // ==============================
    // OFFICIAL SOURCES
    // ==============================
    // Now attached INSIDE message-content
    // so they appear below the text.

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


        const sourceItem = document.createElement("div");

        sourceItem.className = "source-item";


        const sourceNumber = document.createElement("span");

        sourceNumber.className = "source-number";

        sourceNumber.textContent = `${displayIndex}.`;


        const sourceLink = document.createElement("a");

        sourceLink.className = "source-link";

        sourceLink.href = source;
        sourceLink.target = "_blank";
        sourceLink.rel = "noopener noreferrer";

        sourceLink.textContent = getSourceName(source);


        sourceItem.appendChild(sourceNumber);
        sourceItem.appendChild(sourceLink);

        sourceBox.appendChild(sourceItem);

    });


    // Only attach if at least one valid source
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


        const path = parsed.pathname
            .replace(/^\/|\/$/g, "");


        if (!path) {
            return "TMU Official Website";
        }


        const parts = path.split("/");

        const lastPart = parts[parts.length - 1];


        const name = lastPart
            .replace(/[-_]/g, " ")
            .replace(/\b\w/g, letter =>
                letter.toUpperCase()
            );


        // Better names for common TMU pages
        const names = {

            "exam overview":
                "TMU Examination Overview",

            "exam ordinance":
                "TMU Examination Ordinance",

            "cbcs circulars":
                "TMU CBCS Circulars",

            "notice list":
                "TMU Notice Board",

            "scholarship":
                "TMU Scholarships",

            "policies sops":
                "TMU Policies & SOPs"
        };


        const lowerName = name.toLowerCase();


        if (names[lowerName]) {
            return names[lowerName];
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
        Math.min(
            messageInput.scrollHeight,
            150
        ) + "px";
}


messageInput.addEventListener("input", autoResize);


// ==============================
// ENTER TO SEND
// ==============================

messageInput.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();

        }

    }
);


sendBtn.addEventListener("click", sendMessage);


// ==============================
// QUICK QUESTIONS
// ==============================

document
    .querySelectorAll("[data-question]")
    .forEach(
        (button) => {

            button.addEventListener(
                "click",
                () => {

                    const question = button.dataset.question;


                    messageInput.value = question;

                    autoResize();

                    sendMessage();


                    sidebar.classList.remove("open");

                }
            );

        }
    );


// ==============================
// NEW CHAT
// ==============================

newChatBtn.addEventListener(
    "click",
    () => {

        messages.innerHTML = "";

        welcome.style.display = "block";

        messageInput.value = "";

        autoResize();

        messageInput.focus();

        sidebar.classList.remove("open");

    }
);


autoResize();


// ==============================
// RESOURCES + ABOUT
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


    close.addEventListener(
        "click",
        () => overlay.remove()
    );


    header.appendChild(heading);
    header.appendChild(close);


    const body = document.createElement("div");

    body.className = "info-modal-body";

    body.innerHTML = content;


    modal.appendChild(header);
    modal.appendChild(body);


    overlay.appendChild(modal);


    overlay.addEventListener(
        "click",
        (event) => {

            if (event.target === overlay) {
                overlay.remove();
            }

        }
    );


    document.body.appendChild(overlay);
}


// ==============================
// RESOURCES
// ==============================

function openResources() {

    createInfoModal(
        "TMU Resources",

        `
        <p class="modal-description">
            Useful official TMU resources for students.
        </p>

        <div class="resource-grid">

            <a
                href="https://www.tmu.ac.in/tmu/exam-overview"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">📝</span>
                <span>
                    <strong>Examination Overview</strong>
                    <small>Exam rules and attendance requirements</small>
                </span>
            </a>


            <a
                href="https://www.tmu.ac.in/tmu/exam-ordinance"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">📋</span>
                <span>
                    <strong>Examination Ordinance</strong>
                    <small>Official examination ordinances</small>
                </span>
            </a>


            <a
                href="https://www.tmu.ac.in/tmu/cbcs-circulars"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">📢</span>
                <span>
                    <strong>CBCS Circulars</strong>
                    <small>University circulars and updates</small>
                </span>
            </a>


            <a
                href="https://www.tmu.ac.in/notice-list"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">🔔</span>
                <span>
                    <strong>Notice Board</strong>
                    <small>Latest official university notices</small>
                </span>
            </a>


            <a
                href="https://www.tmu.ac.in/tmu/scholarship"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">🎓</span>
                <span>
                    <strong>Scholarships</strong>
                    <small>Scholarship opportunities and guidelines</small>
                </span>
            </a>


            <a
                href="https://www.tmu.ac.in/tmu/policies-sops"
                target="_blank"
                rel="noopener noreferrer"
                class="resource-card"
            >
                <span class="resource-icon">📚</span>
                <span>
                    <strong>Policies &amp; SOPs</strong>
                    <small>Official university policies and procedures</small>
                </span>
            </a>

        </div>
        `
    );
}


// ==============================
// ABOUT
// ==============================

function openAbout() {

    createInfoModal(
        "About TMU AI Assistant",

        `
        <div class="about-content">

            <div class="about-logo">
                🤖
            </div>

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

                <p>
                    Ms. Anvesha Sisodiya
                </p>

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

        const text = item.textContent
            .trim()
            .toLowerCase();


        if (text.includes("resources")) {

            item.addEventListener(
                "click",
                (event) => {

                    event.preventDefault();

                    openResources();

                    sidebar.classList.remove("open");

                }
            );

        }


        if (text.includes("about")) {

            item.addEventListener(
                "click",
                (event) => {

                    event.preventDefault();

                    openAbout();

                    sidebar.classList.remove("open");

                }
            );

        }

    });
}


setupInfoButtons();


// ==============================
// ESCAPE CLOSES MODAL
// ==============================

document.addEventListener(
    "keydown",
    (event) => {

        if (event.key === "Escape") {

            const modal = document.getElementById("infoModal");

            if (modal) {
                modal.remove();
            }

        }

    }
);