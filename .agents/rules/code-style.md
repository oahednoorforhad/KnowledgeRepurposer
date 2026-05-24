---
trigger: always_on
---

The 5 Universal Antigravity Rules
1. The YAGNI Concrete Rule: Write Code for Today, Not Imaginary Tomorrow
Never build an abstraction (like an abstract base class, a generic interface, or a multi-tenant wrapper) until you have at least two distinct concrete use cases requiring it right now.

If you think, "We might need this feature next month," do not write it. Delete the thought.

2. The KISS Pipeline: Data In, Data Out
Break your software down into a linear pipeline of pure or mostly pure functions.

Avoid complex state management or global variables. If Component A needs to talk to Component C, pass the data explicitly through Component B. Magic configurations breed spaghetti code.

3. The SOLID Foundation: The "Single Responsibility" Metric
A class or module should do one conceptual job.

The Litmus Test: If you describe what a file does and you use the word "and", it is too big. (e.g., "This class parses the URL and saves it to the database." Split it into a parser class and a repository class).

4. The DRY Boundary: Don't De-duplicate Too Early
Duplication is far cheaper than the wrong abstraction.

Copying and pasting code twice is completely fine. The third time you copy-paste it, extract it into a shared utility function or service.

5. Zero-Dependency Prototyping
Write your core business logic using the native capabilities of your programming language first.

Do not pull in heavy external frameworks, database connections, or cloud SDKs until your core logic can be proven and verified in a simple terminal script.

🏗 The Universal Step-by-Step Micro-Development Process
Follow this exact loop for any feature, module, or project you build:

Plaintext
[Step 1: Mock Input/Output] 
         ↓
[Step 2: Linear Script (The Ugly Stage)] 
         ↓
[Step 3: Refactor to Pure Functions (KISS)] 
         ↓
[Step 4: Decouple & Encapsulate (SOLID)] 
         ↓
[Step 5: Bind to External Gravity (DB, API, UI)]
Step 1: Define the Static I/O (Input/Output)
Before writing logic, define exactly what goes in and what comes out. Create a hardcoded mock file or mock data structure representing the ideal state.

Example: If building a payment system, create a static text file of a fake transaction payload.

Step 2: Write a Linear Script (The "Ugly" Stage)
Write a raw, top-to-bottom script that transforms your input into your output. Ignore design patterns, bypass classes, and forget elegance.

Goal: Prove technical feasibility. Make it work first.

Step 3: Extract into Pure Functions (Apply KISS & DRY)
Look at your messy script. Identify logical chunks and extract them into individual functions.

Ensure these functions are predictable: given the exact same input, they must always return the exact same output.

At this stage, test these functions locally using basic print statements or assertion tests.

Step 4: Group into Single-Responsibility Classes (Apply SOLID)
Move your functions into specialized classes or modules based on their domain:

The Ingestion Layer: Responsible only for gathering input (web scraping, file reading, API listening).

The Core Logic Layer: Responsible only for processing that data (calculations, formatting, AI orchestration).

The Output/Adapter Layer: Responsible only for sending data away (saving to file, printing to console).

Step 5: Bind External Gravity (DB, Queues, UI)
Only after the core logic layer is perfectly stable should you introduce external complexity ("gravity"):

Hook up your live database instead of mock data.

Wrap your classes in an API framework (like FastAPI, Express, Next.js).

Build the user interface.

The "Am I Over-Engineering?" Checklist
Run through this brief checklist whenever you feel your project slowing down or becoming confusing:

[ ] The 30-Second Rule: Can a developer who has never seen this project look at a file and understand its core purpose within 30 seconds?

[ ] The Delete Test: Can I delete or swap out my database/UI layer without rewriting my core business calculations? (If yes, your architecture is beautifully decoupled).

[ ] Framework bloat: Did I install a massive library or package to solve a problem that could be written in 10 lines of native code?

[ ] Premature Optimization: Am I spending hours worrying about speed, database indexing, or caching before the app even functions correctly for a single user?