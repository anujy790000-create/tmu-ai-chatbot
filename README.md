# TMU AI Student Assistant

An AI-powered chatbot developed by **Anuj Yadav** to help students find information about **Teerthanker Mahaveer University (TMU), Moradabad** using publicly available information from official TMU webpages and documents.

The system uses **Retrieval-Augmented Generation (RAG)** to retrieve relevant information from a locally collected TMU knowledge base and uses an AI model through OpenRouter to generate concise answers.

---

## Project Overview

**TMU AI Student Assistant** is a student-focused AI chatbot designed to make university information easier to find.

Instead of manually searching through multiple TMU webpages, notices, and PDF documents, students can ask questions in natural language and receive relevant answers along with the official TMU sources used.

### Project Information

* **Project Name:** TMU AI Student Assistant
* **Developer:** Anuj Yadav
* **University:** Teerthanker Mahaveer University, Moradabad
* **Course:** BCA
* **Project Type:** Academic / Final-Year Project
* **Technology:** Python, FastAPI, HTML, CSS, JavaScript, RAG, OpenRouter

---

## Problem

Students frequently need information about:

* Attendance requirements
* Examination rules
* Scholarships
* Academic calendars
* University notices
* Important academic information
* University resources

The required information is available on the official TMU website but can be spread across multiple webpages, PDFs, notices, and circulars.

Searching through all of these sources manually can be time-consuming.

---

## Solution

The **TMU AI Student Assistant** provides a conversational interface where students can ask questions naturally.

The system:

1. Collects publicly available TMU webpages and PDFs.
2. Extracts and processes the available information.
3. Stores the processed information in a local knowledge base.
4. Splits the information into searchable chunks.
5. Searches for the most relevant information for each question.
6. Sends relevant context to an AI model through OpenRouter.
7. Generates a concise answer.
8. Displays official TMU source links related to the answer.

The system is designed to answer using the available TMU knowledge base rather than relying only on the general knowledge of the AI model.

---

## Features

* AI-powered student chatbot
* ChatGPT-style conversational interface
* Retrieval-Augmented Generation (RAG)
* Uses official TMU webpages and PDFs as the knowledge source
* Official source links displayed with answers
* Keyword and topic-based relevance search
* Source-priority scoring
* Basic conversation memory for follow-up questions
* Dark / light theme
* Responsive interface
* Desktop and mobile support
* Quick-question shortcuts
* Resources section
* About section
* Privacy information
* Handles questions for which relevant information cannot be found
* No student login required
* No personal student information stored

---

## Important Privacy Boundary

This project uses **public information only**.

It does **not** connect to or access:

* TMU ERP
* Student login accounts
* Personal attendance records
* Personal marks
* Examination results
* Fee records
* Private student information
* Any information behind authentication

For example, if a student asks:

> "What is my attendance percentage?"

the chatbot cannot provide the student's personal attendance because it has no access to private TMU student records.

---

## Tech Stack

| Layer                | Technology                                       |
| -------------------- | ------------------------------------------------ |
| Programming Language | Python                                           |
| Backend              | FastAPI                                          |
| Server               | Uvicorn                                          |
| AI                   | OpenRouter                                       |
| AI SDK               | OpenAI Python SDK                                |
| RAG                  | Custom keyword + topic + source-priority scoring |
| Web Scraping         | Requests + BeautifulSoup4                        |
| PDF Processing       | pypdf                                            |
| Frontend             | HTML + CSS + JavaScript                          |
| Configuration        | python-dotenv                                    |

The project does not require a traditional database or external vector database.

---

## Project Structure

```text
Ai chatbot For College/
│
├── backend/
│   └── main.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── rag/
│   ├── search.py
│   └── generator.py
│
├── scrapper/
│   └── tmu_scraper.py
│
├── data/
│   └── tmu_data.txt
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

### Main Files

| File                      | Purpose                                        |
| ------------------------- | ---------------------------------------------- |
| `backend/main.py`         | FastAPI backend and chat API                   |
| `frontend/index.html`     | Main chatbot interface                         |
| `frontend/style.css`      | User interface styling and responsive design   |
| `frontend/script.js`      | Frontend interaction and chatbot functionality |
| `rag/search.py`           | Knowledge-base search and relevance ranking    |
| `rag/generator.py`        | OpenRouter AI generation                       |
| `scrapper/tmu_scraper.py` | Collects public TMU webpages and PDFs          |
| `data/tmu_data.txt`       | Generated TMU knowledge base                   |
| `.env`                    | Stores API configuration locally               |
| `requirements.txt`        | Python dependencies                            |

---

## System Architecture

```text
                    Official TMU Website
                            │
                            ▼
                    TMU Web Scraper
                            │
                            ▼
                 Webpages and PDF Data
                            │
                            ▼
                    Text Extraction
                            │
                            ▼
                     Knowledge Base
                            │
                            ▼
                     Text Chunking
                            │
                            ▼
                  Relevance Searching
                            │
                            ▼
                  Relevant TMU Context
                            │
                            ▼
                    OpenRouter LLM
                            │
                            ▼
                    Generated Answer
                            │
                            ▼
              Official TMU Source Links
                            │
                            ▼
                     Student Chat UI
```

---

## How the RAG System Works

The project uses a lightweight Retrieval-Augmented Generation approach.

When a student asks a question:

### 1. User Question

The student enters a question into the chatbot.

Example:

```text
What is the attendance requirement?
```

### 2. Retrieval

The system searches the local TMU knowledge base and identifies content related to attendance.

### 3. Relevance Ranking

The retrieved content is ranked using factors such as:

* Keyword relevance
* Topic relevance
* Source priority
* Matching content

### 4. AI Generation

The relevant information is provided to the AI model through OpenRouter.

### 5. Response

The AI generates a concise response based on the retrieved information.

### 6. Sources

The chatbot also provides the relevant official TMU source links.

---

## Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd "Ai chatbot For College"
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### Activate the Environment

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**

```cmd
venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure OpenRouter

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

The API key can be obtained from:

https://openrouter.ai/keys

Do not upload the `.env` file to GitHub.

### 5. Build the TMU Knowledge Base

Run:

```bash
python scrapper/tmu_scraper.py
```

The scraper collects publicly available TMU information and generates:

```text
data/tmu_data.txt
```

### 6. Start the Backend

```bash
python -m uvicorn backend.main:app --reload
```

The backend will run at:

```text
http://127.0.0.1:8000
```

### 7. Start the Frontend

The frontend can be opened directly using:

```text
frontend/index.html
```

Or run a local server:

```bash
python -m http.server 5500 --directory frontend
```

Then open:

```text
http://127.0.0.1:5500
```

---

## Example Questions

Students can ask questions such as:

```text
What is the attendance requirement?
```

```text
What scholarships are available?
```

```text
When are the upcoming examinations?
```

```text
Show me the latest TMU notices.
```

```text
Where can I find the academic calendar?
```

```text
What are the examination rules?
```

```text
Show me useful TMU resources.
```

The chatbot retrieves relevant information and provides the available official TMU sources.

---

## Official TMU Website

The primary source for university information is:

https://www.tmu.ac.in/

Important or time-sensitive information should always be verified against the latest official TMU notice or webpage.

---

## Privacy

The project is designed around publicly available information.

* No student authentication
* No ERP integration
* No personal student records
* No personal attendance access
* No personal marks access
* No personal result access
* No personal fee information
* No storage of personal student information
* Conversation memory exists only during the running session
* Session memory is cleared when the backend restarts

---

## Limitations

* The system depends on the information available in the knowledge base.
* Free OpenRouter models may have rate limits.
* AI responses may occasionally be delayed.
* Scanned PDFs without selectable text may not be processed because OCR is not currently included.
* The knowledge base needs to be refreshed when new university information becomes available.
* Time-sensitive information should be verified using the latest official TMU source.
* Free hosting platforms may put the backend to sleep after inactivity.

---

## Future Scope

The project can be further improved by adding:

* Automated periodic scraping
* Better handling of latest/current information
* Improved document date detection
* More advanced semantic search
* OCR support for scanned PDFs
* Improved conversation context
* API rate limiting
* Better error handling
* Deployment on cloud platforms
* Additional official TMU resources
* Improved response speed
* More advanced source verification

---

## Project Status

The core chatbot has been developed with:

* Frontend interface
* Backend API
* RAG-based information retrieval
* TMU web scraping
* PDF text extraction
* OpenRouter AI integration
* Official source links
* Quick questions
* Resources section
* About section
* Theme switching
* Responsive interface
* Privacy boundaries

---

## Developer

**Name:** Anuj Yadav

**Course:** BCA

**University:** Teerthanker Mahaveer University, Moradabad

**Location:** Moradabad, Uttar Pradesh, India

**GitHub:** https://github.com/anujy790000-create

**Email:** Add your email address

**LinkedIn:** Add your LinkedIn profile

**Project Guide:** To be added

**Academic Year:** 2026–2027

---

## Acknowledgements

* Teerthanker Mahaveer University for the publicly available information used by this project.
* OpenRouter for providing access to AI models.
* FastAPI for the backend framework.
* BeautifulSoup4 for HTML parsing and web scraping.
* pypdf for PDF text extraction.
* The Python and open-source communities.

---

## Disclaimer

This project is an **independent student academic project** developed by Anuj Yadav.

It is **not affiliated with, operated by, or officially endorsed by Teerthanker Mahaveer University's IT department or administration**.

TMU names, trademarks, logos, and other university-related intellectual property belong to their respective owners.

The chatbot is intended to make publicly available university information easier to find. Students should verify important, official, or time-sensitive information through the official TMU website and university notices.

---

## License

This project is an independent academic project created for educational purposes.

Third-party libraries, APIs, services, and other components used by the project remain subject to their respective licenses and terms of use.

---

## Author

**Anuj Yadav**

BCA Student
Teerthanker Mahaveer University, Moradabad

GitHub: https://github.com/anujy790000-create
