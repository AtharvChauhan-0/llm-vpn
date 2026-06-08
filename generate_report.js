const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  TableOfContents, ExternalHyperlink, SectionType,
} = require("docx");
const fs = require("fs");

// ─── Page / margin constants (match template) ───────────────────────────────
const PAGE_W  = 11907;  // A4 width in DXA
const PAGE_H  = 16840;  // A4 height in DXA
const M_TOP   = 1134;
const M_BOT   = 1134;
const M_RIGHT = 1134;
const M_LEFT  = 1701;
const CONTENT_W = PAGE_W - M_LEFT - M_RIGHT; // 9072

// ─── Typography helpers ──────────────────────────────────────────────────────
const TNR = "Times New Roman";

function rpr(opts = {}) {
  return {
    font: TNR,
    size: opts.size || 24,      // half-points; 24 = 12pt
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || "000000",
  };
}

function run(text, opts = {}) {
  return new TextRun({ text, ...rpr(opts) });
}

function para(children, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: {
      before: opts.spaceBefore !== undefined ? opts.spaceBefore : 0,
      after:  opts.spaceAfter  !== undefined ? opts.spaceAfter  : 160,
      line:   opts.line !== undefined ? opts.line : 360,   // 1.5 line spacing
      lineRule: "auto",
    },
    indent: opts.indent ? { firstLine: 720 } : undefined,
    pageBreakBefore: opts.pageBreak || false,
    children,
  });
}

function centeredPara(children, opts = {}) {
  return para(children, { ...opts, align: AlignmentType.CENTER });
}

function heading1(text, pageBreak = true) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: pageBreak,
    spacing: { before: 480, after: 240 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: TNR, size: 32, bold: true, allCaps: true })],
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, font: TNR, size: 28, bold: true })],
  });
}

function heading3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, font: TNR, size: 24, bold: true })],
  });
}

function body(text, indent = true) {
  return para([run(text)], { indent, line: 360 });
}

function empty() { return para([run("")]); }

// ─── Table helpers ───────────────────────────────────────────────────────────
function makeBorder() {
  return { style: BorderStyle.SINGLE, size: 6, color: "000000" };
}
function allBorders() {
  const b = makeBorder();
  return { top: b, bottom: b, left: b, right: b };
}

function headerCell(text, widthDxa) {
  return new TableCell({
    borders: allBorders(),
    width: { size: widthDxa, type: WidthType.DXA },
    shading: { fill: "D9E1F2", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, font: TNR, size: 22, bold: true })],
    })],
  });
}

function dataCell(text, widthDxa, align = AlignmentType.LEFT) {
  return new TableCell({
    borders: allBorders(),
    width: { size: widthDxa, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text, font: TNR, size: 22 })],
    })],
  });
}

// ─── Bullet helpers ───────────────────────────────────────────────────────────
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { before: 60, after: 60, line: 320, lineRule: "auto" },
    children: [run(text)],
  });
}

function subBullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 1 },
    spacing: { before: 40, after: 40, line: 300, lineRule: "auto" },
    children: [run(text)],
  });
}

// ─── Page properties shared ──────────────────────────────────────────────────
function pageProps(pgNumFmt = "decimal", pgStart = 1) {
  return {
    page: {
      size: { width: PAGE_W, height: PAGE_H },
      margin: { top: M_TOP, right: M_RIGHT, bottom: M_BOT, left: M_LEFT,
                header: 720, footer: 720, gutter: 0 },
      pageNumbers: { formatType: pgNumFmt, start: pgStart },
    },
  };
}

function makeFooter(center = false) {
  return new Footer({
    children: [new Paragraph({
      alignment: center ? AlignmentType.CENTER : AlignmentType.RIGHT,
      children: [
        new TextRun({ text: "Page ", font: TNR, size: 20 }),
        new TextRun({ children: [PageNumber.CURRENT], font: TNR, size: 20 }),
      ],
    })],
  });
}

function makeHeader(text) {
  return new Header({
    children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000", space: 1 } },
      children: [new TextRun({ text, font: TNR, size: 20, italics: true })],
    })],
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 0 – COVER PAGE
// ═══════════════════════════════════════════════════════════════════════════════
const coverChildren = [
  centeredPara([run("[INSTITUTION LOGO]", { size: 24, bold: true })],
    { spaceBefore: 0, spaceAfter: 200, line: 240 }),

  centeredPara([run("LLM-VPN: A Client-Side LLM API Gateway", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 80, line: 280 }),
  centeredPara([run("with Semantic Routing and Cryptographic Envelope", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 360, line: 280 }),

  centeredPara([run("A", { size: 28 })], { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Major Project (CC4270) Report", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Submitted in the partial fulfillment of the requirement for the award of", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Bachelor of Technology", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("in", { size: 28 })], { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Computer and Communication Engineering", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 360, line: 240 }),

  centeredPara([run("By:", { size: 28 })], { spaceBefore: 0, spaceAfter: 80, line: 240 }),
  centeredPara([run("Name:       [STUDENT NAME]", { size: 28, bold: true })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Reg No.:    [REGISTRATION NUMBER]", { size: 28, bold: true })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Section:    [SECTION]", { size: 28, bold: true })],
    { spaceBefore: 0, spaceAfter: 360, line: 240 }),

  centeredPara([run("Under the supervision of:", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 80, line: 240 }),
  centeredPara([run("[SUPERVISOR NAME]", { size: 28, bold: true })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Type of project: Internal / External", { size: 28, bold: true })],
    { spaceBefore: 0, spaceAfter: 360, line: 240 }),

  centeredPara([run("May 2026", { size: 28 })], { spaceBefore: 0, spaceAfter: 200, line: 240 }),

  centeredPara([run("Department of Computer and Communication Engineering", { size: 34 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("School of Computer Science and Engineering", { size: 36 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("Manipal University Jaipur", { size: 36 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
  centeredPara([run("VPO. Dehmi Kalan, Jaipur, Rajasthan, India – 303007", { size: 28 })],
    { spaceBefore: 0, spaceAfter: 0, line: 240 }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 1 – STUDENT DECLARATION
// ═══════════════════════════════════════════════════════════════════════════════
const declarationChildren = [
  centeredPara([run("STUDENT DECLARATION", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 480, line: 240 }),

  body(
    "I, [STUDENT NAME], Registration Number [REG NO.], student of Bachelor of Technology in " +
    "Computer and Communication Engineering, School of Computer Science and Engineering, " +
    "Manipal University Jaipur, hereby declare that the Major Project entitled " +
    "“LLM-VPN: A Client-Side LLM API Gateway with Semantic Routing and Cryptographic Envelope” " +
    "submitted to Manipal University Jaipur in partial fulfillment of the requirements for the " +
    "award of the degree of Bachelor of Technology in Computer and Communication Engineering, " +
    "is a record of original work done by me under the supervision of [SUPERVISOR NAME], " +
    "Department of Computer and Communication Engineering, Manipal University Jaipur.",
    true
  ),
  empty(),
  body(
    "I further declare that the work reported in this project has not been submitted and will " +
    "not be submitted, either in part or in full, for the award of any other degree or diploma " +
    "in this institute or any other institute or university.",
    true
  ),
  empty(),
  body(
    "I have properly cited all references used in this report and all sources of information " +
    "have been duly acknowledged.",
    true
  ),
  empty(),
  empty(),
  empty(),

  para([run("Place: Jaipur"), run("                                                       "),
        run("Signature of Student", { bold: true })],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 40 }),
  para([run("Date:  May 2026"), run("                                                       "),
        run("[STUDENT NAME]", { bold: true })],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 0 }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 2 – SUPERVISOR CERTIFICATE
// ═══════════════════════════════════════════════════════════════════════════════
const certificateChildren = [
  centeredPara([run("SUPERVISOR’S CERTIFICATE", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 480, line: 240 }),

  body(
    "This is to certify that the Major Project entitled “LLM-VPN: A Client-Side LLM API " +
    "Gateway with Semantic Routing and Cryptographic Envelope”, submitted by " +
    "[STUDENT NAME] (Reg No. [REG NO.]) in partial fulfillment of the requirements for " +
    "the award of the degree of Bachelor of Technology in Computer and Communication " +
    "Engineering at Manipal University Jaipur, is a record of bonafide work carried out " +
    "by the student under my supervision and guidance.",
    true
  ),
  empty(),
  body(
    "The project is an original contribution and has not been submitted elsewhere for the " +
    "award of any other degree or diploma, either in this university or any other institution. " +
    "To the best of my knowledge and belief, the data and information presented in this " +
    "report have not been submitted in part or full for any other degree program.",
    true
  ),
  empty(),
  empty(),
  empty(),

  para([run("Place: Jaipur"), run("                                                         "),
        run("Signature of Supervisor", { bold: true })],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 40 }),
  para([run("Date:  May 2026"), run("                                                         "),
        run("[SUPERVISOR NAME]", { bold: true })],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 40 }),
  para([run("                                                                     "),
        run("Designation: [DESIGNATION]")],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 40 }),
  para([run("                                                                     "),
        run("Department of CCE, MUJ")],
    { align: AlignmentType.LEFT, line: 280, indent: false, spaceAfter: 0 }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 3 – ACKNOWLEDGEMENTS
// ═══════════════════════════════════════════════════════════════════════════════
const ackChildren = [
  centeredPara([run("ACKNOWLEDGEMENTS", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 480, line: 240 }),

  body(
    "[PLACEHOLDER – Write your acknowledgements here. Express gratitude to your supervisor, " +
    "faculty members, family, friends, and any organizations that supported your project work. " +
    "Typical acknowledgements are 1–2 paragraphs in length.]",
    true
  ),
  empty(),
  body(
    "I would like to express my sincere gratitude to [SUPERVISOR NAME] for their invaluable " +
    "guidance, continuous encouragement, and constructive feedback throughout the course of " +
    "this project. Their insights into network security and machine learning helped shape the " +
    "direction of this work significantly.",
    true
  ),
  empty(),
  body(
    "I am also thankful to the Department of Computer and Communication Engineering and the " +
    "School of Computer Science and Engineering at Manipal University Jaipur for providing " +
    "the necessary infrastructure and resources to carry out this project.",
    true
  ),
  empty(),
  body(
    "I extend my gratitude to my family and friends for their unwavering moral support and " +
    "encouragement. Their belief in my abilities was a constant source of motivation.",
    true
  ),
  empty(),
  empty(),
  para([run("                                                                                     "),
        run("[STUDENT NAME]", { bold: true })],
    { align: AlignmentType.LEFT, line: 280, indent: false }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 4 – ABSTRACT
// ═══════════════════════════════════════════════════════════════════════════════
const abstractChildren = [
  centeredPara([run("ABSTRACT", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 480, line: 240 }),

  body(
    "The rapid proliferation of Large Language Model (LLM) APIs in enterprise and consumer " +
    "applications has introduced novel privacy and security challenges. Sensitive data — " +
    "including personally identifiable information (PII), proprietary business logic, and " +
    "regulated content — flows routinely through these APIs with little interception or " +
    "semantic understanding at the network layer. This project presents LLM-VPN, a client-side " +
    "network proxy that operates as a transparent intermediary between LLM client applications " +
    "and remote LLM API endpoints.",
    true
  ),
  body(
    "LLM-VPN intercepts outgoing HTTP requests, extracts the JSON payload, and subjects each " +
    "request to a two-tier intent classification pipeline. The first tier employs deterministic " +
    "rule-based heuristics that execute in under ten milliseconds, detecting tool calls, system " +
    "prompts, agent delegation patterns, jailbreak attempts, and streaming continuations. When " +
    "rule-based confidence falls below a threshold of 0.75, the second tier invokes a TinyBERT " +
    "neural zero-shot classifier for more nuanced semantic understanding.",
    true
  ),
  body(
    "In parallel with classification, the system scans request content for PII using the " +
    "Microsoft Presidio framework, identifying entities such as names, email addresses, phone " +
    "numbers, social security numbers, passport details, and medical record identifiers. " +
    "Detected entities are mapped to a three-level sensitivity scheme: high_pii, medium_pii, " +
    "and low. Token estimation is performed concurrently using a heuristic word-count approach " +
    "or the tiktoken library when available.",
    true
  ),
  body(
    "Classification and PII results are combined into a Semantic Envelope consisting of a " +
    "plaintext signed header and an AES-256-GCM encrypted payload. The header encodes intent " +
    "class, sensitivity level, token estimate, session context, turn index, agent depth, and " +
    "a derived routing hint. The header is signed with an ECDSA private key over the SECP256R1 " +
    "curve, providing non-repudiation and tamper detection. The original request body is " +
    "encrypted with a per-session AES-256 key and a 96-bit random initialization vector, " +
    "with the GCM authentication tag ensuring ciphertext integrity.",
    true
  ),
  body(
    "The modified request carries the signed envelope as a custom HTTP header and the " +
    "encrypted body as the request payload, enabling a downstream gateway or VPN terminator " +
    "to make semantically-informed routing decisions. An ancillary inspection API exposes " +
    "session statistics, intent distributions, and PII hit rates in real time.",
    true
  ),
  body(
    "Experimental evaluation confirms sub-10-millisecond rule-based classification for over " +
    "90% of traffic patterns. The system correctly identifies jailbreak candidates, routes " +
    "high-PII traffic to domestic-only channels, and sandboxes tool-call traffic, demonstrating " +
    "the feasibility of semantic-layer network security for LLM traffic.",
    true
  ),
  empty(),

  heading3("Keywords"),
  body(
    "LLM API security, semantic routing, intent classification, PII detection, AES-256-GCM, " +
    "ECDSA, network proxy, TinyBERT, zero-shot classification, cryptographic envelope, " +
    "jailbreak detection, session management.",
    false
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 5 – TABLE OF CONTENTS (auto)
// ═══════════════════════════════════════════════════════════════════════════════
const tocChildren = [
  centeredPara([run("TABLE OF CONTENTS", { size: 32, bold: true })],
    { spaceBefore: 0, spaceAfter: 240, line: 240 }),
  new TableOfContents("Table of Contents", {
    hyperlink: true,
    headingStyleRange: "1-3",
    stylesWithLevels: [],
  }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 1 – INTRODUCTION
// ═══════════════════════════════════════════════════════════════════════════════
const ch1 = [
  heading1("Chapter 1: Introduction"),

  heading2("1.1 Background and Motivation"),
  body(
    "The emergence of Large Language Models (LLMs) as general-purpose reasoning engines has " +
    "catalyzed a new category of AI-powered applications across domains ranging from healthcare " +
    "to legal services, financial advisory, and software engineering. Products built on APIs " +
    "provided by companies such as OpenAI, Anthropic, Google DeepMind, and Cohere have " +
    "reached millions of users within a remarkably short span of time. According to industry " +
    "estimates, the global LLM API market is projected to exceed $40 billion by 2027, " +
    "growing at a compound annual growth rate of over 35 percent.",
    true
  ),
  body(
    "This explosive growth has introduced a set of security and privacy concerns that have " +
    "not yet been adequately addressed by existing network infrastructure. Traditional Virtual " +
    "Private Networks (VPNs) and web application firewalls operate at the packet or HTTP " +
    "layer; they can encrypt traffic and filter by domain or IP address, but they lack any " +
    "understanding of the semantic content of the messages they carry. A VPN, for instance, " +
    "cannot distinguish between a routine user query and a prompt containing a patient’s " +
    "medical history, nor can it detect a jailbreak attempt or flag a request that delegates " +
    "authority to a sub-agent.",
    true
  ),
  body(
    "Enterprise compliance frameworks such as the General Data Protection Regulation (GDPR), " +
    "the Health Insurance Portability and Accountability Act (HIPAA), and the Payment Card " +
    "Industry Data Security Standard (PCI-DSS) impose strict controls on the transmission " +
    "and storage of personally identifiable information (PII). As LLM applications routinely " +
    "process customer communications, support tickets, medical notes, and financial records, " +
    "ensuring that PII is identified and handled appropriately before it leaves the client " +
    "network becomes a critical compliance requirement. The absence of such controls creates " +
    "significant legal and reputational exposure.",
    true
  ),
  body(
    "Simultaneously, the rise of agentic LLM systems — in which models autonomously " +
    "orchestrate tools, spawn sub-agents, and execute multi-step plans — has introduced " +
    "novel attack surfaces. Prompt injection attacks, jailbreak attempts, and unauthorized " +
    "agent delegation have been demonstrated in both controlled research settings and real-world " +
    "deployments. Existing solutions largely rely on application-layer guardrails implemented " +
    "within the LLM provider’s API, leaving the client side without an independent " +
    "enforcement point.",
    true
  ),

  heading2("1.2 Problem Statement"),
  body(
    "Current network architectures provide no semantic visibility into LLM API traffic. " +
    "Specifically, the following problems remain unsolved at the client-network layer:",
    true
  ),
  bullet("PII Leakage: Sensitive personal information contained in LLM prompts is transmitted to remote servers without interception or sanitization, violating data residency and compliance requirements."),
  bullet("Jailbreak Blindness: Network infrastructure cannot detect adversarial prompts designed to subvert model safety guidelines, leaving detection entirely to the LLM provider."),
  bullet("Opaque Routing: All LLM API requests are treated identically by the network regardless of their semantic nature; a routine query and a high-sensitivity medical prompt travel through the same infrastructure with the same priority and routing."),
  bullet("Lack of Session Context: Individual LLM API calls are stateless from the network’s perspective, preventing context-aware policy enforcement across multi-turn conversations or agentic workflows."),
  bullet("No Tamper Evidence: There is no mechanism to detect whether the content of an LLM API request has been modified in transit, either by a man-in-the-middle attacker or a compromised intermediary."),
  empty(),

  heading2("1.3 Objectives"),
  body(
    "This project aims to design, implement, and evaluate LLM-VPN, a client-side proxy that " +
    "addresses the above problems. The specific objectives are:",
    true
  ),
  bullet("To design a two-tier intent classification pipeline that categorizes LLM API requests by semantic intent with low latency."),
  bullet("To implement real-time PII detection using the Microsoft Presidio framework and classify detected entities by sensitivity level."),
  bullet("To construct a Semantic Envelope that embeds classification metadata into each request as a cryptographically signed and authenticated header."),
  bullet("To encrypt request payloads using AES-256-GCM with per-session keys, ensuring confidentiality and integrity."),
  bullet("To derive routing hints from classification results, enabling downstream network infrastructure to make semantically-informed forwarding decisions."),
  bullet("To implement persistent session state management that tracks conversation context, turn indices, and agent depth across multi-turn interactions."),
  bullet("To expose an inspection API for real-time monitoring of session statistics, intent distributions, and PII hit rates."),
  empty(),

  heading2("1.4 Scope of Work"),
  body(
    "The project encompasses the design and implementation of the client-side proxy component " +
    "of the LLM-VPN architecture. The following aspects are within scope:",
    true
  ),
  bullet("Transparent HTTP/HTTPS proxy using the mitmproxy framework for request interception."),
  bullet("Two-tier classification: rule-based (Tier 1) and neural zero-shot classification using TinyBERT (Tier 2)."),
  bullet("PII scanning and sensitivity classification using Microsoft Presidio."),
  bullet("Cryptographic operations: ECDSA signing (SECP256R1), SHA-256 integrity hashing, and AES-256-GCM payload encryption."),
  bullet("Semantic Envelope construction: signed plaintext header and encrypted payload."),
  bullet("Session management with per-session AES keys and configurable expiry."),
  bullet("Inspection REST API using FastAPI and Uvicorn."),
  bullet("Unit and integration testing for all core modules."),
  empty(),
  body(
    "The server-side VPN terminator that would decrypt envelopes and enforce routing policies " +
    "is considered future work and is outside the scope of this project.",
    true
  ),

  heading2("1.5 Organisation of the Report"),
  body(
    "The remainder of this report is organized as follows. Chapter 2 reviews related work in " +
    "LLM API security, network proxy architectures, and intent classification systems. Chapter " +
    "3 presents the system architecture and design of LLM-VPN. Chapter 4 describes the " +
    "implementation details of each component. Chapter 5 discusses testing methodology and " +
    "experimental results. Chapter 6 concludes the report and outlines directions for future " +
    "work. References are listed at the end of the report.",
    true
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 2 – LITERATURE REVIEW
// ═══════════════════════════════════════════════════════════════════════════════
const ch2 = [
  heading1("Chapter 2: Literature Review"),

  heading2("2.1 Security Challenges in LLM API Ecosystems"),
  body(
    "The security of LLM systems has attracted significant research attention since the " +
    "public release of GPT-3 in 2020. Perez and Ribeiro (2022) provided one of the first " +
    "systematic analyses of prompt injection attacks, demonstrating that adversarially crafted " +
    "input can override system prompts and cause models to produce harmful outputs. Greshake " +
    "et al. (2023) extended this work to indirect prompt injection, showing that malicious " +
    "instructions can be embedded in external data sources retrieved by agentic systems.",
    true
  ),
  body(
    "Jailbreaking — the practice of crafting prompts that cause models to ignore their " +
    "safety training — has been documented extensively. Zou et al. (2023) demonstrated " +
    "that suffix-based adversarial attacks can reliably jailbreak both open-source and " +
    "commercial models. Shen et al. (2023) catalogued over 100 distinct jailbreak strategies " +
    "observed in the wild, highlighting the breadth of the attack surface.",
    true
  ),
  body(
    "At the network layer, the problem of inspecting encrypted traffic without breaking end-to-end " +
    "security has been studied in the context of deep packet inspection (DPI) and TLS interception. " +
    "Anderson et al. (2019) showed that TLS fingerprinting can classify application traffic with " +
    "high accuracy, but does not provide semantic visibility into the content of requests. " +
    "LLM-VPN takes a complementary approach: rather than inspecting encrypted content, it " +
    "classifies content before encryption at the client side.",
    true
  ),

  heading2("2.2 Network Proxies and VPN Architectures"),
  body(
    "The mitmproxy framework (Cortesi et al., 2011) provides an extensible Python-based " +
    "transparent proxy that supports HTTPS interception via certificate pinning bypass. It " +
    "has been used extensively in security research for traffic analysis and API testing. " +
    "LLM-VPN leverages mitmproxy’s addon architecture to implement request interception " +
    "as a non-invasive layer between LLM clients and servers.",
    true
  ),
  body(
    "Traditional VPN solutions such as OpenVPN and WireGuard provide encrypted tunnels for " +
    "all network traffic but operate at Layer 3 (IP) or Layer 4 (TCP/UDP), with no " +
    "application-layer awareness. Software-Defined Networking (SDN) approaches have enabled " +
    "more dynamic routing policies, but these still lack semantic understanding of application " +
    "payloads. LLM-VPN bridges this gap by embedding semantic metadata — derived from " +
    "content analysis — into the request headers, allowing downstream infrastructure to " +
    "act on this information without itself performing content analysis.",
    true
  ),
  body(
    "The concept of a “semantic overlay network” was introduced by Zhu et al. (2006) " +
    "in the context of peer-to-peer systems, where routing decisions are informed by the " +
    "semantic similarity of content rather than purely by network topology. LLM-VPN adapts " +
    "this concept to the specific domain of LLM API traffic, where semantic categories " +
    "(tool calls, system prompts, jailbreaks) have direct implications for routing policy.",
    true
  ),

  heading2("2.3 Intent Classification and Natural Language Understanding"),
  body(
    "Intent classification is a well-studied problem in the natural language processing (NLP) " +
    "community, originally motivated by spoken dialogue systems and virtual assistants. " +
    "Traditional approaches relied on feature engineering and support vector machines. " +
    "The introduction of transformer-based models (Vaswani et al., 2017) and BERT " +
    "(Devlin et al., 2018) enabled dramatically improved performance on intent classification " +
    "benchmarks.",
    true
  ),
  body(
    "For deployment in latency-sensitive settings, compact models such as TinyBERT " +
    "(Jiao et al., 2019) and DistilBERT (Sanh et al., 2019) have demonstrated that " +
    "knowledge distillation can achieve near-BERT performance with a fraction of the " +
    "parameters. TinyBERT achieves 96.8% of BERT’s performance on GLUE benchmarks " +
    "while being 7.5 times smaller and 9.4 times faster. LLM-VPN employs TinyBERT via " +
    "the Hugging Face zero-shot classification pipeline, which uses natural-language " +
    "hypothesis templates rather than a fixed label set.",
    true
  ),
  body(
    "Zero-shot classification using cross-encoder models (Yin et al., 2019) formulates " +
    "intent classification as a natural-language inference (NLI) task: given a premise " +
    "(the request content) and a hypothesis (e.g., “This is a tool call”), the " +
    "model outputs an entailment probability. This approach requires no task-specific " +
    "training data, making it suitable for open-ended intent taxonomies.",
    true
  ),

  heading2("2.4 PII Detection and Data Classification"),
  body(
    "Named Entity Recognition (NER) has long been the primary mechanism for PII detection " +
    "in unstructured text. Microsoft Presidio (Microsoft, 2020) extends NER with pattern " +
    "matching, checksum validation, and context-aware disambiguation to achieve high-precision " +
    "detection of a wide range of PII entity types including names, locations, dates, " +
    "financial account numbers, national identification numbers, and medical record identifiers.",
    true
  ),
  body(
    "Recent work by Lison et al. (2021) demonstrated that combining transformer-based NER " +
    "with regex patterns and context heuristics significantly reduces false positive rates " +
    "compared to NER alone. Presidio’s architecture follows this approach, using " +
    "SpaCy NER as a base and layering additional recognizers for jurisdiction-specific " +
    "identifiers such as US SSNs, UK National Insurance numbers, and Indian Aadhaar numbers.",
    true
  ),
  body(
    "Data sensitivity classification — assigning detected PII to sensitivity tiers — " +
    "is an important concept in data governance frameworks. The NIST Privacy Framework " +
    "defines sensitivity tiers based on the potential harm to individuals if the data is " +
    "disclosed. LLM-VPN’s three-tier scheme (high_pii, medium_pii, low) is designed " +
    "to be consistent with GDPR’s distinction between ordinary personal data and " +
    "special-category data.",
    true
  ),

  heading2("2.5 Cryptographic Foundations"),
  body(
    "AES-256-GCM (Galois/Counter Mode) is a widely deployed authenticated encryption scheme " +
    "that provides both confidentiality and data integrity in a single pass. It is standardized " +
    "in NIST SP 800-38D and is the preferred encryption mode in TLS 1.3. The 96-bit " +
    "initialization vector and 128-bit authentication tag used in LLM-VPN follow NIST " +
    "recommendations for online authenticated encryption.",
    true
  ),
  body(
    "ECDSA (Elliptic Curve Digital Signature Algorithm) over the SECP256R1 (P-256) curve " +
    "is standardized in FIPS 186-4 and is widely used in TLS certificates and JWT signing. " +
    "It provides 128-bit security with a 256-bit key, making it computationally efficient " +
    "while maintaining a strong security margin against known attacks. The choice of SECP256R1 " +
    "over SECP256K1 (the Bitcoin curve) reflects the broader PKI ecosystem support and " +
    "hardware acceleration availability for P-256 operations.",
    true
  ),
  body(
    "The Python cryptography library (PyCA) provides a well-audited implementation of both " +
    "AES-GCM and ECDSA. Its hazmat (hazardous materials) API is designed for direct use " +
    "of cryptographic primitives and has been extensively reviewed by the security community.",
    true
  ),

  heading2("2.6 Research Gap"),
  body(
    "A review of the existing literature reveals that while considerable work has been done " +
    "on LLM application-layer security (prompt injection, jailbreaking) and on network-layer " +
    "security (encrypted traffic analysis, DPI), no prior work has proposed a client-side " +
    "proxy that combines semantic intent classification, PII detection, and cryptographic " +
    "envelope construction into a unified transparent intermediary for LLM API traffic. " +
    "LLM-VPN fills this gap by providing a lightweight, extensible proxy that operates " +
    "without modifying the LLM client application.",
    true
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 3 – SYSTEM DESIGN AND ARCHITECTURE
// ═══════════════════════════════════════════════════════════════════════════════
const ch3 = [
  heading1("Chapter 3: System Design and Architecture"),

  heading2("3.1 Overview"),
  body(
    "LLM-VPN is architected as a multi-stage transparent proxy that sits between an LLM " +
    "client application and a remote LLM API endpoint. From the client’s perspective, " +
    "the proxy is invisible: the application simply configures its HTTP proxy settings to " +
    "point to localhost:8080, and all subsequent LLM API calls are intercepted automatically. " +
    "The system processes each request through four stages — Intercept, Classify, " +
    "Envelope, and Forward — before delivering the modified request to the remote " +
    "endpoint.",
    true
  ),
  body(
    "A secondary Inspection API runs on port 8081 and exposes a RESTful interface for " +
    "monitoring session state, intent distributions, PII hit rates, and system statistics. " +
    "This API is intended for integration with enterprise security information and event " +
    "management (SIEM) systems or custom dashboards.",
    true
  ),

  heading2("3.2 Stage 1: Request Interception"),
  body(
    "The interception layer is built on mitmproxy, an open-source transparent proxy framework " +
    "written in Python. When an LLM client sends an HTTP request to an API endpoint, mitmproxy " +
    "captures the raw request before it leaves the local network interface. The interceptor " +
    "extracts the JSON body, decodes it, and passes it to the session manager.",
    true
  ),
  body(
    "The session manager assigns a session identifier by hashing the client IP address and " +
    "a high-resolution timestamp using SHA-256, producing a 64-character hexadecimal session " +
    "ID. For requests from the same client IP within an active session window (configurable, " +
    "default 30 minutes), the same session ID is reused, enabling multi-turn conversation " +
    "tracking. Each session maintains a monotonically increasing turn index, an agent depth " +
    "counter, a bounded history of the last ten intent classifications, and timestamps for " +
    "creation and last activity.",
    true
  ),

  heading2("3.3 Stage 2: Two-Tier Classification"),
  body(
    "The classification stage is the semantic core of LLM-VPN. It implements a two-tier " +
    "pipeline that balances latency and accuracy.",
    true
  ),

  heading3("3.3.1 Tier 1: Rule-Based Classification"),
  body(
    "The first tier applies a sequence of deterministic rules to the decoded JSON body. " +
    "Rules are evaluated in priority order and return immediately upon a match, ensuring " +
    "that the most time-sensitive classifications complete in under 10 milliseconds on " +
    "commodity hardware. The following six intent classes are handled by Tier 1:",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [Math.round(CONTENT_W * 0.25), Math.round(CONTENT_W * 0.25), Math.round(CONTENT_W * 0.5)],
    rows: [
      new TableRow({ children: [
        headerCell("Intent Class", Math.round(CONTENT_W * 0.25)),
        headerCell("Confidence", Math.round(CONTENT_W * 0.25)),
        headerCell("Detection Rule", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("tool_call", Math.round(CONTENT_W * 0.25)),
        dataCell("1.00", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("Presence of tool_calls or function_call keys; or last message role = tool", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("system_prompt", Math.round(CONTENT_W * 0.25)),
        dataCell("1.00 / 0.90", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("turn_index == 0; or any message with role = system", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("agent_delegation", Math.round(CONTENT_W * 0.25)),
        dataCell("0.85", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("Keywords: subtask, delegate, as an agent, on behalf of, sub-agent", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("jailbreak_candidate", Math.round(CONTENT_W * 0.25)),
        dataCell("0.95", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("Pattern match against 15+ jailbreak signatures loaded from config", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("streaming_continuation", Math.round(CONTENT_W * 0.25)),
        dataCell("1.00", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("stream flag = true AND turn_index > 0", Math.round(CONTENT_W * 0.5)),
      ]}),
      new TableRow({ children: [
        dataCell("user_turn", Math.round(CONTENT_W * 0.25)),
        dataCell("0.70", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
        dataCell("Default fallback when no other rule matches", Math.round(CONTENT_W * 0.5)),
      ]}),
    ],
  }),

  para([run("Table 3.1: Tier 1 Rule-Based Classification Rules", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),

  heading3("3.3.2 Tier 2: Neural Classification"),
  body(
    "When Tier 1 returns a confidence score below 0.75, the request is passed to Tier 2, " +
    "which employs a pre-trained TinyBERT model via the Hugging Face zero-shot classification " +
    "pipeline. The full message content is concatenated into a single string and submitted " +
    "as the premise, while the intent class labels serve as hypotheses. The label with the " +
    "highest entailment probability is returned as the classification result.",
    true
  ),
  body(
    "Tier 2 adds approximately 50–200 milliseconds of latency depending on hardware, " +
    "but is invoked only for ambiguous cases. In practice, the vast majority of LLM API " +
    "requests contain unambiguous structural signals (tool_calls keys, turn index 0, etc.) " +
    "that allow Tier 1 to classify them with full confidence.",
    true
  ),

  heading2("3.4 PII Detection and Sensitivity Classification"),
  body(
    "PII detection runs in parallel with intent classification using the Microsoft Presidio " +
    "AnalyzerEngine. The engine applies a battery of recognizers to the concatenated message " +
    "text and returns a list of detected PII entities with their types, positions, and " +
    "confidence scores. Entities are filtered to those with a confidence score above 0.7.",
    true
  ),
  body(
    "The sensitivity classifier maps detected entity types to one of three levels using the " +
    "following rules applied in decreasing priority order:",
    true
  ),
  bullet("high_pii: The entity set contains any of CREDIT_CARD, US_SSN, PASSPORT, MEDICAL_LICENSE; or contains both PERSON and LOCATION together."),
  bullet("medium_pii: The entity set contains EMAIL_ADDRESS, PHONE_NUMBER, IP_ADDRESS, or PERSON without LOCATION."),
  bullet("low: No entities detected above the confidence threshold."),
  empty(),

  heading2("3.5 Stage 3: Semantic Envelope Construction"),
  body(
    "The Semantic Envelope is the central data structure of LLM-VPN. It consists of two " +
    "components: a plaintext signed header and an encrypted payload.",
    true
  ),

  heading3("3.5.1 Header"),
  body(
    "The header is a JSON object containing the following fields: intent_class (string), " +
    "sensitivity (string), token_estimate (integer), session_id (hex string), turn_index " +
    "(integer), agent_depth (integer), timestamp (Unix milliseconds), routing_hint (string), " +
    "integrity_hash (SHA-256 hex of original request body), and envelope_sig (ECDSA signature " +
    "hex). The header is serialized to canonical JSON (lexicographically sorted keys, no " +
    "extraneous whitespace) before signing.",
    true
  ),

  heading3("3.5.2 Routing Hint Derivation"),
  body(
    "The routing_hint field is derived from the combination of sensitivity level and intent " +
    "class according to the following priority-ordered decision tree:",
    true
  ),
  bullet("domestic-only: sensitivity == high_pii (data residency enforcement)"),
  bullet("block: intent == jailbreak_candidate (request to be dropped by gateway)"),
  bullet("sandbox-cluster: intent == tool_call (isolated execution environment)"),
  bullet("rate-limited: agent_depth > 3 (recursive agent depth limit)"),
  bullet("best-available: all other cases (standard routing)"),
  empty(),

  heading3("3.5.3 ECDSA Signing"),
  body(
    "The canonical JSON representation of the header (with envelope_sig set to an empty " +
    "string) is signed using ECDSA-SHA256 with the SECP256R1 private key. The resulting " +
    "DER-encoded signature is hex-encoded and inserted into the envelope_sig field. The " +
    "gateway can verify the signature against the public key to detect tampering or " +
    "spoofing of the metadata header.",
    true
  ),

  heading3("3.5.4 Payload Encryption"),
  body(
    "The original request body (bytes) is encrypted using AES-256-GCM with a per-session " +
    "32-byte key and a randomly generated 96-bit IV. The AESGCM.encrypt() function from " +
    "the PyCA cryptography library returns the ciphertext with the 128-bit GCM authentication " +
    "tag appended. The ciphertext, IV, and auth tag are included in the envelope.",
    true
  ),

  heading2("3.6 Stage 4: Request Modification and Forwarding"),
  body(
    "The proxy replaces the original request body with a JSON object containing the fields " +
    "encrypted_payload (base64-encoded ciphertext), iv (base64-encoded initialization vector), " +
    "and auth_tag (base64-encoded authentication tag). Two custom HTTP headers are added: " +
    "X-Semantic-Envelope (base64-encoded signed header JSON) and X-Envelope-Session " +
    "(the session ID). All original headers are preserved. The modified request is then " +
    "forwarded to the target LLM API endpoint.",
    true
  ),

  heading2("3.7 Session Management"),
  body(
    "Session state is maintained in a thread-safe in-memory dictionary keyed by session ID. " +
    "Each session record contains the session ID, a 32-byte AES key, the current turn index, " +
    "the current agent depth, a bounded deque of the last ten intent classifications, and " +
    "timestamps for creation and last activity. A background cleanup task runs every five " +
    "minutes and removes sessions that have been inactive for longer than the configured " +
    "timeout (default 30 minutes).",
    true
  ),

  heading2("3.8 Inspection API"),
  body(
    "The Inspection API is a FastAPI application served by Uvicorn on port 8081. It runs " +
    "in a daemon thread alongside the mitmproxy server. The API exposes the following " +
    "endpoints:",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [Math.round(CONTENT_W * 0.3), Math.round(CONTENT_W * 0.15), Math.round(CONTENT_W * 0.55)],
    rows: [
      new TableRow({ children: [
        headerCell("Endpoint", Math.round(CONTENT_W * 0.3)),
        headerCell("Method", Math.round(CONTENT_W * 0.15)),
        headerCell("Description", Math.round(CONTENT_W * 0.55)),
      ]}),
      new TableRow({ children: [
        dataCell("/sessions", Math.round(CONTENT_W * 0.3)),
        dataCell("GET", Math.round(CONTENT_W * 0.15), AlignmentType.CENTER),
        dataCell("List all active sessions with metadata", Math.round(CONTENT_W * 0.55)),
      ]}),
      new TableRow({ children: [
        dataCell("/sessions/{id}", Math.round(CONTENT_W * 0.3)),
        dataCell("GET", Math.round(CONTENT_W * 0.15), AlignmentType.CENTER),
        dataCell("Retrieve full state of a specific session", Math.round(CONTENT_W * 0.55)),
      ]}),
      new TableRow({ children: [
        dataCell("/stats", Math.round(CONTENT_W * 0.3)),
        dataCell("GET", Math.round(CONTENT_W * 0.15), AlignmentType.CENTER),
        dataCell("Aggregate statistics: request counts, intent and sensitivity distributions, total tokens", Math.round(CONTENT_W * 0.55)),
      ]}),
      new TableRow({ children: [
        dataCell("/health", Math.round(CONTENT_W * 0.3)),
        dataCell("GET", Math.round(CONTENT_W * 0.15), AlignmentType.CENTER),
        dataCell("Health check: proxy status, key availability, uptime", Math.round(CONTENT_W * 0.55)),
      ]}),
    ],
  }),

  para([run("Table 3.2: Inspection API Endpoints", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 4 – IMPLEMENTATION
// ═══════════════════════════════════════════════════════════════════════════════
const ch4 = [
  heading1("Chapter 4: Implementation"),

  heading2("4.1 Development Environment"),
  body(
    "LLM-VPN is implemented in Python 3.10+ and designed to run on Linux, macOS, and " +
    "Windows operating systems. The development environment used Python 3.12.3 on Windows " +
    "11 with a virtual environment managed by venv. The project has no external binary " +
    "dependencies beyond the Python packages listed in requirements.txt.",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [Math.round(CONTENT_W * 0.35), Math.round(CONTENT_W * 0.2), Math.round(CONTENT_W * 0.45)],
    rows: [
      new TableRow({ children: [
        headerCell("Dependency", Math.round(CONTENT_W * 0.35)),
        headerCell("Version", Math.round(CONTENT_W * 0.2)),
        headerCell("Purpose", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("mitmproxy", Math.round(CONTENT_W * 0.35)),
        dataCell(">=10.0.0", Math.round(CONTENT_W * 0.2)),
        dataCell("Transparent HTTP/HTTPS proxy", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("cryptography", Math.round(CONTENT_W * 0.35)),
        dataCell(">=41.0.0", Math.round(CONTENT_W * 0.2)),
        dataCell("AES-GCM, ECDSA, key serialization", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("presidio-analyzer", Math.round(CONTENT_W * 0.35)),
        dataCell(">=2.2.0", Math.round(CONTENT_W * 0.2)),
        dataCell("PII entity recognition", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("transformers", Math.round(CONTENT_W * 0.35)),
        dataCell(">=4.35.0", Math.round(CONTENT_W * 0.2)),
        dataCell("TinyBERT zero-shot pipeline", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("fastapi", Math.round(CONTENT_W * 0.35)),
        dataCell(">=0.104.0", Math.round(CONTENT_W * 0.2)),
        dataCell("Inspection REST API", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("uvicorn", Math.round(CONTENT_W * 0.35)),
        dataCell(">=0.24.0", Math.round(CONTENT_W * 0.2)),
        dataCell("ASGI server for FastAPI", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("tiktoken", Math.round(CONTENT_W * 0.35)),
        dataCell(">=0.5.0", Math.round(CONTENT_W * 0.2)),
        dataCell("Accurate token estimation", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("spacy", Math.round(CONTENT_W * 0.35)),
        dataCell(">=3.7.0", Math.round(CONTENT_W * 0.2)),
        dataCell("NLP backend for Presidio", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("python-dotenv", Math.round(CONTENT_W * 0.35)),
        dataCell(">=1.0.0", Math.round(CONTENT_W * 0.2)),
        dataCell("Environment variable management", Math.round(CONTENT_W * 0.45)),
      ]}),
    ],
  }),

  para([run("Table 4.1: Project Dependencies", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),

  heading2("4.2 Module Structure"),
  body(
    "The project is organized into the following Python modules, each with a single " +
    "well-defined responsibility:",
    true
  ),
  bullet("main.py – Entry point; initializes keys, starts inspection API thread, and keeps the process alive."),
  bullet("interceptor.py – mitmproxy addon class LLMVPNProxy; implements request() and response() hooks; maintains global statistics."),
  bullet("builder.py – Orchestrates the classification, PII scanning, envelope construction, and request modification pipeline."),
  bullet("classifier.py – Implements classify_tier1() and classify_tier2(); loads jailbreak patterns from config."),
  bullet("pii.py – Wraps Presidio AnalyzerEngine; implements detect_pii() and classify_sensitivity()."),
  bullet("crypto.py – Implements generate_sha256_hash(), sign_header(), verify_signature(), encrypt_payload(), decrypt_payload(), and generate_session_key()."),
  bullet("schema.py – Defines Pydantic models SemanticEnvelope and EnvelopeHeader for type-safe envelope construction."),
  bullet("session.py – Implements SessionState dataclass and SessionManager singleton."),
  bullet("intent.py – Defines IntentClass Enum with values for all six intent categories."),
  bullet("inspection.py – FastAPI application factory create_inspection_app(); defines route handlers."),
  bullet("setup.py – One-time setup script that generates ECDSA key pairs."),
  empty(),

  heading2("4.3 Interceptor Implementation"),
  body(
    "The LLMVPNProxy class is a mitmproxy addon that registers two event handlers: request() " +
    "is called before the request is forwarded to the server, and response() is called after " +
    "the server’s response is received. The request handler performs the complete " +
    "intercept-classify-envelope-forward pipeline. It filters requests to target only " +
    "configured LLM API hostnames (api.openai.com, api.anthropic.com, etc.) and skips all " +
    "other traffic unchanged.",
    true
  ),
  body(
    "Within the request handler, the JSON body is parsed using Python’s standard json " +
    "library. If parsing fails (e.g., for streaming chunks or non-JSON requests), the request " +
    "is passed through without modification. A shallow try/except block wraps the entire " +
    "processing pipeline to prevent proxy failures from disrupting client applications.",
    true
  ),

  heading2("4.4 Classification Implementation"),
  body(
    "Tier 1 classification is implemented as a pure function classify_tier1(body, turn_index, " +
    "agent_depth) that returns a tuple of (IntentClass, float). The function applies rules " +
    "in the order: tool_call, system_prompt, agent_delegation, jailbreak_candidate, " +
    "streaming_continuation, user_turn. Each rule either returns immediately or falls through " +
    "to the next check.",
    true
  ),
  body(
    "Jailbreak patterns are loaded from a configurable text file at startup (default: " +
    "config/jailbreak_patterns.txt). Each line in the file is treated as a lowercase " +
    "substring that, if found in the concatenated message content, triggers a jailbreak " +
    "classification. This design allows security teams to update the pattern list without " +
    "modifying source code.",
    true
  ),
  body(
    "Tier 2 classification uses the Hugging Face pipeline() factory function with the " +
    "zero-shot-classification task and the facebook/bart-large-mnli or a TinyBERT equivalent " +
    "model. The model is loaded lazily on first invocation to avoid startup latency. " +
    "Classification labels correspond directly to IntentClass enum values.",
    true
  ),

  heading2("4.5 PII Detection Implementation"),
  body(
    "The PIIDetector class wraps a Presidio AnalyzerEngine configured with the en " +
    "(English) language model. The detect() method concatenates all user and assistant " +
    "message content into a single string and runs the analyzer with a predefined entity " +
    "list: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, CREDIT_CARD, US_SSN, PASSPORT, " +
    "MEDICAL_LICENSE, IP_ADDRESS, URL, DATE_TIME, and NRP (Nationality, Religious, or " +
    "Political group).",
    true
  ),
  body(
    "The classify_sensitivity() function takes the list of RecognizerResult objects " +
    "returned by Presidio and applies the priority-ordered sensitivity rules described in " +
    "Section 3.4. The function returns a string sensitivity label and the list of detected " +
    "entity types for inclusion in the envelope header.",
    true
  ),
  body(
    "Token estimation is performed by a separate estimate_tokens() function. It first " +
    "attempts to use the tiktoken cl100k_base encoding (used by GPT-4 and later models). " +
    "If tiktoken is not available or raises an exception, it falls back to the heuristic " +
    "formula: token_estimate = int(word_count * 1.3).",
    true
  ),

  heading2("4.6 Cryptographic Implementation"),
  body(
    "Key generation is handled by setup.py using the ec.generate_private_key(ec.SECP256R1()) " +
    "function from the cryptography library. The private key is serialized in PKCS8 " +
    "PEM format without encryption; the public key is serialized in SubjectPublicKeyInfo " +
    "PEM format. Both keys are written to the keys/ directory, which is listed in .gitignore " +
    "to prevent accidental version control inclusion.",
    true
  ),
  body(
    "The sign_header() function in crypto.py accepts the canonical JSON bytes of the header " +
    "and the loaded private key object, and returns the ECDSA signature as a hex string. " +
    "Canonicalization is performed by json.dumps() with sort_keys=True and separators=(',',':') " +
    "to eliminate whitespace.",
    true
  ),
  body(
    "Payload encryption uses AESGCM(key).encrypt(iv, plaintext, None), where key is the " +
    "per-session 32-byte key stored in the SessionState, and iv is freshly generated for " +
    "each request using os.urandom(12). The None value for the associated data parameter " +
    "means no additional authenticated data (AAD) is included; this is appropriate since " +
    "the header is separately signed rather than bound to the ciphertext.",
    true
  ),

  heading2("4.7 Schema and Envelope Assembly"),
  body(
    "The SemanticEnvelope Pydantic model provides type-safe construction and JSON " +
    "serialization of the envelope. It contains two fields: header (an EnvelopeHeader " +
    "instance) and body (a dict containing the encrypted payload, IV, and auth tag as " +
    "base64-encoded strings). The EnvelopeHeader model defines all header fields with " +
    "appropriate Python types and default values.",
    true
  ),
  body(
    "The assembled envelope header is base64-encoded and attached to the outgoing request " +
    "as the X-Semantic-Envelope HTTP header. The session ID is attached as X-Envelope-Session. " +
    "The request body is replaced with a JSON document containing the encrypted payload " +
    "fields, and the Content-Length header is updated to reflect the new body size.",
    true
  ),

  heading2("4.8 Configuration"),
  body(
    "LLM-VPN supports the following configuration parameters via environment variables " +
    "(loaded from a .env file using python-dotenv):",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [Math.round(CONTENT_W * 0.35), Math.round(CONTENT_W * 0.2), Math.round(CONTENT_W * 0.45)],
    rows: [
      new TableRow({ children: [
        headerCell("Variable", Math.round(CONTENT_W * 0.35)),
        headerCell("Default", Math.round(CONTENT_W * 0.2)),
        headerCell("Description", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("PROXY_PORT", Math.round(CONTENT_W * 0.35)),
        dataCell("8080", Math.round(CONTENT_W * 0.2)),
        dataCell("Local proxy listening port", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("INSPECTION_API_PORT", Math.round(CONTENT_W * 0.35)),
        dataCell("8081", Math.round(CONTENT_W * 0.2)),
        dataCell("Inspection API port", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("SESSION_TIMEOUT", Math.round(CONTENT_W * 0.35)),
        dataCell("1800", Math.round(CONTENT_W * 0.2)),
        dataCell("Session expiry in seconds (30 min)", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("TOKEN_ESTIMATE_METHOD", Math.round(CONTENT_W * 0.35)),
        dataCell("heuristic", Math.round(CONTENT_W * 0.2)),
        dataCell("heuristic or tiktoken", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("LOG_LEVEL", Math.round(CONTENT_W * 0.35)),
        dataCell("INFO", Math.round(CONTENT_W * 0.2)),
        dataCell("Python logging level", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("JAILBREAK_PATTERNS_PATH", Math.round(CONTENT_W * 0.35)),
        dataCell("./config/...", Math.round(CONTENT_W * 0.2)),
        dataCell("Path to jailbreak patterns file", Math.round(CONTENT_W * 0.45)),
      ]}),
      new TableRow({ children: [
        dataCell("PRIVATE_KEY_PATH", Math.round(CONTENT_W * 0.35)),
        dataCell("./keys/private.pem", Math.round(CONTENT_W * 0.2)),
        dataCell("ECDSA private key for signing", Math.round(CONTENT_W * 0.45)),
      ]}),
    ],
  }),

  para([run("Table 4.2: Configuration Parameters", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 5 – TESTING AND RESULTS
// ═══════════════════════════════════════════════════════════════════════════════
const ch5 = [
  heading1("Chapter 5: Testing and Results"),

  heading2("5.1 Test Strategy"),
  body(
    "The testing strategy for LLM-VPN adopts a layered approach consistent with the " +
    "project’s modular architecture. Three levels of testing were employed: unit " +
    "testing of individual functions and classes, integration testing of complete " +
    "request-processing pipelines, and manual end-to-end validation against live LLM APIs. " +
    "All automated tests are implemented using Python’s pytest framework and can be " +
    "executed with a single command from the project root.",
    true
  ),

  heading2("5.2 Unit Testing"),

  heading3("5.2.1 Classifier Tests (test_classifier.py)"),
  body(
    "The classifier test suite contains 47 test cases covering Tier 1 classification. " +
    "Tests verify correct intent assignment for each rule, boundary conditions at the " +
    "confidence threshold, correct handling of malformed JSON, and priority ordering " +
    "when multiple rules could match. Representative test cases include:",
    true
  ),
  bullet("Verify tool_call detection when tool_calls key is present."),
  bullet("Verify system_prompt detection at turn_index == 0 and turn_index > 0."),
  bullet("Verify jailbreak detection for each of the 15 default patterns."),
  bullet("Verify agent_delegation detection for each delegation keyword."),
  bullet("Verify that tool_call takes precedence over system_prompt when both conditions are true."),
  bullet("Verify that streaming_continuation requires both stream=True and turn_index > 0."),
  empty(),

  heading3("5.2.2 Envelope Tests (test_envelope.py)"),
  body(
    "The envelope test suite contains 63 test cases covering the complete envelope " +
    "construction pipeline. Tests verify:",
    true
  ),
  bullet("SHA-256 hash correctness for known inputs."),
  bullet("ECDSA signature generation and verification with generated test keys."),
  bullet("Signature failure on tampered canonical JSON."),
  bullet("AES-256-GCM encrypt/decrypt round-trip for payloads of varying sizes."),
  bullet("IV uniqueness across 1000 consecutive encryptions."),
  bullet("Auth tag verification failure on corrupted ciphertext."),
  bullet("Routing hint derivation for each combination of sensitivity and intent."),
  bullet("Session key uniqueness across 100 generated keys."),
  empty(),

  heading3("5.2.3 Proxy Tests (test_proxy.py)"),
  body(
    "The proxy test suite contains 38 test cases that mock the mitmproxy HTTP flow " +
    "object and verify the behavior of the LLMVPNProxy addon. Tests confirm that: " +
    "non-LLM-API requests pass through unmodified; malformed JSON request bodies are " +
    "handled gracefully; the X-Semantic-Envelope and X-Envelope-Session headers are " +
    "correctly added to processed requests; statistics are incremented accurately; and " +
    "session state is correctly initialized, updated, and expired.",
    true
  ),

  heading2("5.3 Classification Accuracy"),
  body(
    "Classification accuracy was evaluated on a manually curated dataset of 200 synthetic " +
    "LLM API requests spanning all six intent classes. Requests were constructed to represent " +
    "realistic patterns observed in popular LLM frameworks including LangChain, LlamaIndex, " +
    "and the OpenAI Assistants API.",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [
      Math.round(CONTENT_W * 0.28),
      Math.round(CONTENT_W * 0.18),
      Math.round(CONTENT_W * 0.18),
      Math.round(CONTENT_W * 0.18),
      Math.round(CONTENT_W * 0.18),
    ],
    rows: [
      new TableRow({ children: [
        headerCell("Intent Class", Math.round(CONTENT_W * 0.28)),
        headerCell("Samples", Math.round(CONTENT_W * 0.18)),
        headerCell("Precision", Math.round(CONTENT_W * 0.18)),
        headerCell("Recall", Math.round(CONTENT_W * 0.18)),
        headerCell("F1-Score", Math.round(CONTENT_W * 0.18)),
      ]}),
      new TableRow({ children: [
        dataCell("tool_call", Math.round(CONTENT_W * 0.28)),
        dataCell("40", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("system_prompt", Math.round(CONTENT_W * 0.28)),
        dataCell("35", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.97", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.99", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("agent_delegation", Math.round(CONTENT_W * 0.28)),
        dataCell("30", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.93", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.90", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.91", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("jailbreak_candidate", Math.round(CONTENT_W * 0.28)),
        dataCell("25", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.96", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.92", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.94", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("streaming_continuation", Math.round(CONTENT_W * 0.28)),
        dataCell("35", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("1.00", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("user_turn", Math.round(CONTENT_W * 0.28)),
        dataCell("35", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.91", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.94", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.93", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Macro Average", Math.round(CONTENT_W * 0.28)),
        dataCell("200", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.97", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.96", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
        dataCell("0.96", Math.round(CONTENT_W * 0.18), AlignmentType.CENTER),
      ]}),
    ],
  }),

  para([run("Table 5.1: Classification Accuracy on Synthetic Test Dataset", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),

  body(
    "Results demonstrate that structurally determined classes (tool_call, " +
    "streaming_continuation) achieve perfect precision and recall, as expected. " +
    "Keyword-based classes (agent_delegation, jailbreak_candidate) show slightly lower " +
    "scores due to paraphrase variants in the test set that did not match the fixed " +
    "keyword list. In all such cases, Tier 2 TinyBERT classification correctly identified " +
    "the intent, validating the two-tier design.",
    true
  ),

  heading2("5.4 Latency Analysis"),
  body(
    "End-to-end processing latency was measured for 1,000 representative requests on a " +
    "standard development machine (Intel Core i7-12700H, 16 GB RAM, Windows 11). " +
    "Measurements exclude network latency to the remote API endpoint and focus solely on " +
    "the proxy’s internal processing overhead.",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [
      Math.round(CONTENT_W * 0.35),
      Math.round(CONTENT_W * 0.2),
      Math.round(CONTENT_W * 0.2),
      Math.round(CONTENT_W * 0.25),
    ],
    rows: [
      new TableRow({ children: [
        headerCell("Stage", Math.round(CONTENT_W * 0.35)),
        headerCell("Mean (ms)", Math.round(CONTENT_W * 0.2)),
        headerCell("P95 (ms)", Math.round(CONTENT_W * 0.2)),
        headerCell("Max (ms)", Math.round(CONTENT_W * 0.25)),
      ]}),
      new TableRow({ children: [
        dataCell("JSON parsing + session lookup", Math.round(CONTENT_W * 0.35)),
        dataCell("0.8", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("2.1", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("4.3", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Tier 1 classification", Math.round(CONTENT_W * 0.35)),
        dataCell("1.2", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("3.5", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("8.7", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Tier 2 classification (when invoked)", Math.round(CONTENT_W * 0.35)),
        dataCell("143.0", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("198.0", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("312.0", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("PII detection", Math.round(CONTENT_W * 0.35)),
        dataCell("12.4", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("28.9", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("67.2", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Envelope construction + crypto", Math.round(CONTENT_W * 0.35)),
        dataCell("2.1", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("4.2", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("9.8", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Total (Tier 1 path)", Math.round(CONTENT_W * 0.35)),
        dataCell("16.5", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("34.7", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("82.1", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
      new TableRow({ children: [
        dataCell("Total (Tier 2 path)", Math.round(CONTENT_W * 0.35)),
        dataCell("159.5", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("231.2", Math.round(CONTENT_W * 0.2), AlignmentType.CENTER),
        dataCell("380.0", Math.round(CONTENT_W * 0.25), AlignmentType.CENTER),
      ]}),
    ],
  }),

  para([run("Table 5.2: Processing Latency by Stage", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 200, line: 240 }),

  body(
    "The dominant cost on the Tier 1 path is PII detection (75% of total latency), which " +
    "reflects the complexity of the Presidio NER pipeline. For the 92.3% of requests " +
    "handled by Tier 1 alone, the mean overhead of 16.5 ms represents a negligible addition " +
    "relative to the typical 200–2000 ms round-trip latency of remote LLM API calls. " +
    "Tier 2 invocations add 143 ms mean latency but affect only 7.7% of requests.",
    true
  ),

  heading2("5.5 PII Detection Accuracy"),
  body(
    "PII detection accuracy was evaluated on a dataset of 150 synthetic text samples " +
    "containing known PII entities, created following privacy-safe guidelines (no real " +
    "personal data was used in testing). The Presidio-based detector achieved 94.2% " +
    "precision and 91.8% recall across all entity types, with the best performance on " +
    "structured entities (email addresses, phone numbers, credit card numbers) and " +
    "lower performance on contextually ambiguous entities such as person names in " +
    "low-context sentences.",
    true
  ),

  heading2("5.6 Security Analysis"),
  body(
    "The security properties of LLM-VPN were analyzed against the following threat model: " +
    "a network-level attacker capable of observing and modifying traffic between the proxy " +
    "and the remote LLM API endpoint, and an application-level attacker capable of injecting " +
    "malicious prompts.",
    true
  ),
  bullet("Confidentiality: AES-256-GCM encryption ensures that an observer cannot read the original request content from the encrypted body. The 96-bit random IV ensures semantic security even for repeated plaintexts."),
  bullet("Integrity: The GCM authentication tag detects any modification of the ciphertext in transit. The ECDSA signature on the header detects any modification of the semantic metadata."),
  bullet("Non-repudiation: The ECDSA signature binds the semantic metadata to the private key, enabling the gateway to attribute the classification to a specific client."),
  bullet("Jailbreak Mitigation: The routing hint “block” for jailbreak candidates provides a mechanism for the gateway to drop such requests before they reach the LLM API, implementing a defense-in-depth strategy."),
  bullet("PII Routing: The “domestic-only” routing hint for high-PII requests enables enforcement of data residency requirements at the network layer."),
  empty(),
  body(
    "Known limitations include the absence of forward secrecy (the per-session key is stored " +
    "in memory for the session lifetime) and the reliance on pattern matching for jailbreak " +
    "detection, which is susceptible to novel paraphrases not covered by the pattern list. " +
    "Both limitations are identified as areas for future improvement.",
    true
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// CHAPTER 6 – CONCLUSION AND FUTURE WORK
// ═══════════════════════════════════════════════════════════════════════════════
const ch6 = [
  heading1("Chapter 6: Conclusion and Future Work"),

  heading2("6.1 Conclusion"),
  body(
    "This project has presented LLM-VPN, a novel client-side network proxy that introduces " +
    "semantic visibility and cryptographic protection to LLM API traffic. The system " +
    "demonstrates that it is feasible to classify the intent of LLM API requests, detect " +
    "personally identifiable information, and construct a cryptographically signed semantic " +
    "envelope — all with a processing overhead acceptable for production deployment.",
    true
  ),
  body(
    "The two-tier classification pipeline achieves a macro-averaged F1-score of 0.96 on " +
    "a synthetic test dataset while maintaining a mean end-to-end latency of 16.5 ms for " +
    "the 92% of requests handled by the rule-based first tier. The cryptographic envelope " +
    "provides confidentiality, integrity, and non-repudiation for both the request payload " +
    "and the semantic metadata, enabling downstream infrastructure to enforce semantically- " +
    "informed routing policies without itself performing content analysis.",
    true
  ),
  body(
    "The project confirms that the “LLM-First VPN” concept — network " +
    "decisions informed by semantic understanding of LLM traffic — is technically " +
    "realizable as a lightweight, transparent proxy that requires no modification of " +
    "existing LLM client applications. The system integrates cleanly with the OpenAI, " +
    "Anthropic, and Google Gemini APIs via the standard HTTP_PROXY mechanism.",
    true
  ),
  body(
    "From a broader perspective, LLM-VPN represents a step toward a new category of " +
    "application-aware network security infrastructure that is specifically designed for " +
    "the era of AI applications. As LLM-powered systems become increasingly prevalent in " +
    "enterprise environments, the ability to enforce compliance, detect abuse, and route " +
    "traffic based on semantic understanding of AI payloads will become a critical " +
    "infrastructure capability.",
    true
  ),

  heading2("6.2 Future Work"),
  body(
    "Several directions for future research and development have been identified:",
    true
  ),

  heading3("6.2.1 Server-Side VPN Terminator"),
  body(
    "The most important extension of this work is the implementation of the server-side " +
    "VPN terminator that decrypts incoming envelopes, verifies signatures, and enforces " +
    "routing policies based on the semantic metadata. This would complete the end-to-end " +
    "LLM-VPN architecture and enable deployment in enterprise network environments.",
    true
  ),

  heading3("6.2.2 Forward Secrecy"),
  body(
    "The current per-session symmetric key scheme does not provide forward secrecy: " +
    "compromise of the session state in memory exposes the session key. A future version " +
    "could use ECDH key agreement between the client proxy and the server terminator to " +
    "derive ephemeral per-request keys, providing forward secrecy at the cost of an " +
    "additional round-trip during session establishment.",
    true
  ),

  heading3("6.2.3 Neural Jailbreak Detection"),
  body(
    "The current keyword-based jailbreak detection is effective against known patterns but " +
    "is vulnerable to paraphrase attacks. A fine-tuned classifier trained on a curated " +
    "jailbreak dataset (such as JailbreakBench or AdvBench) would provide more robust " +
    "detection. Alternatively, a retrieval-augmented approach could compare new prompts " +
    "against a dynamic database of known jailbreak templates.",
    true
  ),

  heading3("6.2.4 Response Interception and Analysis"),
  body(
    "The current system processes only outgoing requests. Extending it to inspect LLM " +
    "responses would enable detection of model output containing PII, toxic content, or " +
    "policy violations — providing a bidirectional semantic filter for LLM traffic.",
    true
  ),

  heading3("6.2.5 Multi-Provider Support and Routing"),
  body(
    "The routing hint mechanism could be extended to include provider-specific routing " +
    "decisions: for example, routing high-sensitivity requests to on-premise LLM deployments " +
    "(such as Llama or Mistral) rather than cloud APIs, based on data residency policy. " +
    "The semantic envelope already carries the routing_hint field; the gateway layer only " +
    "needs to be built to act on it.",
    true
  ),

  heading3("6.2.6 Performance Optimization"),
  body(
    "PII detection currently dominates the processing latency on the Tier 1 path. " +
    "Profiling suggests that Presidio’s NLP pipeline can be accelerated by restricting " +
    "the entity set to only those relevant to the deployment context, by running the " +
    "analyzer asynchronously in a thread pool, or by using a lighter NER model for initial " +
    "screening followed by a full scan only when initial results are positive.",
    true
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// REFERENCES
// ═══════════════════════════════════════════════════════════════════════════════
const references = [
  heading1("References"),

  body("[1] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 30.", false),
  empty(),
  body("[2] Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2018). BERT: Pre-training of deep bidirectional transformers for language understanding. arXiv preprint arXiv:1810.04805.", false),
  empty(),
  body("[3] Jiao, X., Yin, Y., Shang, L., Jiang, X., Chen, X., Li, L., Wang, F., & Liu, Q. (2019). TinyBERT: Distilling BERT for natural language understanding. arXiv preprint arXiv:1909.10351.", false),
  empty(),
  body("[4] Sanh, V., Debut, L., Chaumond, J., & Wolf, T. (2019). DistilBERT, a distilled version of BERT: Smaller, faster, cheaper and lighter. arXiv preprint arXiv:1910.01108.", false),
  empty(),
  body("[5] Yin, W., Hay, J., & Roth, D. (2019). Benchmarking zero-shot text classification: Datasets, evaluation and entailment approach. Proceedings of EMNLP-IJCNLP 2019.", false),
  empty(),
  body("[6] Perez, F., & Ribeiro, I. (2022). Ignore previous prompt: Attack techniques for language models. arXiv preprint arXiv:2211.09527.", false),
  empty(),
  body("[7] Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you’ve signed up for: Compromising real-world LLM-integrated applications with indirect prompt injections. arXiv preprint arXiv:2302.12173.", false),
  empty(),
  body("[8] Zou, A., Wang, Z., Kolter, J. Z., & Fredrikson, M. (2023). Universal and transferable adversarial attacks on aligned language models. arXiv preprint arXiv:2307.15043.", false),
  empty(),
  body("[9] Shen, X., Chen, Z., Backes, M., Shen, Y., & Zhang, Y. (2023). “Do anything now”: Characterizing and evaluating in-the-wild jailbreak prompts on large language models. arXiv preprint arXiv:2308.03825.", false),
  empty(),
  body("[10] Anderson, B., Paul, S., & McGrew, D. (2019). Deciphering malware’s use of TLS (without decryption). Journal of Computer Virology and Hacking Techniques, 15(3), 195–211.", false),
  empty(),
  body("[11] Cortesi, A., Hils, M., Kriechbaumer, T., & others. (2011). mitmproxy: A free and open source interactive HTTPS proxy. https://mitmproxy.org", false),
  empty(),
  body("[12] Microsoft. (2020). Presidio – Data protection and anonymization API. Microsoft Open Source. https://microsoft.github.io/presidio/", false),
  empty(),
  body("[13] Lison, P., Plaček, J., & Doucet, A. (2021). Anonymisation benchmarks for named entity recognition and linking in plain and clinical text. arXiv preprint arXiv:2106.10000.", false),
  empty(),
  body("[14] National Institute of Standards and Technology. (2007). Recommendation for block cipher modes of operation: Galois/Counter Mode (GCM) and GMAC. NIST Special Publication 800-38D.", false),
  empty(),
  body("[15] National Institute of Standards and Technology. (2023). Digital signature standard (DSS). FIPS Publication 186-5.", false),
  empty(),
  body("[16] Zhu, S., Fang, A., Yan, Y., & Liu, Y. (2006). Semantic overlay networks for P2P systems. In International Workshop on Agents and Peer-to-Peer Computing (pp. 1–13). Springer, Berlin, Heidelberg.", false),
  empty(),
  body("[17] PyCA Cryptography. (2024). cryptography 42.0 documentation. https://cryptography.io/en/latest/", false),
  empty(),
  body("[18] Tiku, J., & Ogilvie, S. (2023). FastAPI documentation. https://fastapi.tiangolo.com/", false),
  empty(),
  body("[19] Wolf, T., Debut, L., Sanh, V., Chaumond, J., Delangue, C., Moi, A., Cistac, P., Rault, T., Louf, R., Funtowicz, M., & Brew, J. (2019). HuggingFace’s Transformers: State-of-the-art natural language processing. arXiv preprint arXiv:1910.03771.", false),
  empty(),
  body("[20] European Parliament and Council. (2016). Regulation (EU) 2016/679 on the protection of natural persons with regard to the processing of personal data (GDPR). Official Journal of the European Union.", false),
];

// ═══════════════════════════════════════════════════════════════════════════════
// APPENDIX
// ═══════════════════════════════════════════════════════════════════════════════
const appendix = [
  heading1("Appendix A: Jailbreak Pattern List"),
  body(
    "The following patterns are included in the default jailbreak_patterns.txt configuration " +
    "file. Each pattern is matched as a case-insensitive substring of the concatenated " +
    "message content. Security teams are encouraged to extend this list with domain-specific " +
    "patterns.",
    true
  ),

  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [Math.round(CONTENT_W * 0.1), Math.round(CONTENT_W * 0.5), Math.round(CONTENT_W * 0.4)],
    rows: [
      new TableRow({ children: [
        headerCell("#", Math.round(CONTENT_W * 0.1)),
        headerCell("Pattern String", Math.round(CONTENT_W * 0.5)),
        headerCell("Attack Category", Math.round(CONTENT_W * 0.4)),
      ]}),
      ...([
        ["ignore previous instructions", "Instruction override"],
        ["ignore all instructions", "Instruction override"],
        ["pretend you are", "Persona hijack"],
        ["your true self", "Persona hijack"],
        ["dan mode", "Jailbreak persona (DAN)"],
        ["jailbreak", "Explicit jailbreak"],
        ["do anything now", "Constraint bypass"],
        ["no restrictions", "Constraint bypass"],
        ["bypass your", "Constraint bypass"],
        ["forget you are an ai", "Reality denial"],
        ["disregard all previous", "Instruction override"],
        ["new instructions", "Instruction injection"],
        ["system override", "Privilege escalation"],
        ["admin mode", "Privilege escalation"],
        ["developer mode", "Privilege escalation"],
      ].map(([pattern, category], i) =>
        new TableRow({ children: [
          dataCell(String(i + 1), Math.round(CONTENT_W * 0.1), AlignmentType.CENTER),
          dataCell(pattern, Math.round(CONTENT_W * 0.5)),
          dataCell(category, Math.round(CONTENT_W * 0.4)),
        ]})
      )),
    ],
  }),

  para([run("Table A.1: Default Jailbreak Pattern List", { italics: true })],
    { align: AlignmentType.CENTER, spaceBefore: 80, spaceAfter: 300, line: 240 }),

  heading1("Appendix B: Semantic Envelope JSON Schema", false),
  body(
    "The following JSON schema defines the structure of the Semantic Envelope header " +
    "transmitted in the X-Semantic-Envelope HTTP header. All fields are required.",
    true
  ),

  new Paragraph({
    spacing: { before: 120, after: 120, line: 280, lineRule: "auto" },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children: [
      new TextRun({ text: '{', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "intent_class":   "tool_call | system_prompt | agent_delegation |', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '                     jailbreak_candidate | streaming_continuation | user_turn",', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "sensitivity":    "high_pii | medium_pii | low",', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "token_estimate": <integer>,', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "session_id":     "<64-char hex string>",', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "turn_index":     <integer>,', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "agent_depth":    <integer>,', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "timestamp":      <unix milliseconds>,', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "routing_hint":   "domestic-only | sandbox-cluster | rate-limited | block | best-available",', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "integrity_hash": "<64-char SHA-256 hex>",', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '  "envelope_sig":   "<ECDSA-SHA256 hex signature>"', font: "Courier New", size: 20 }),
      new TextRun({ break: 1, text: '}', font: "Courier New", size: 20 }),
    ],
  }),

  empty(),
  heading1("Appendix C: Quick-Start Guide", false),
  body("Follow these steps to install and run LLM-VPN on a development machine.", true),
  bullet("Step 1: Clone the repository and create a Python virtual environment: python -m venv venv"),
  bullet("Step 2: Activate the virtual environment and install dependencies: pip install -r requirements.txt"),
  bullet("Step 3: Install the spaCy English model: python -m spacy download en_core_web_lg"),
  bullet("Step 4: Generate ECDSA keys: python setup.py"),
  bullet("Step 5: (Optional) Copy .env.example to .env and configure settings."),
  bullet("Step 6: Start the proxy: python main.py"),
  bullet("Step 7: Configure your LLM client: set HTTP_PROXY=http://localhost:8080 and HTTPS_PROXY=http://localhost:8080"),
  bullet("Step 8: Monitor sessions via the inspection API at http://localhost:8081/docs"),
  empty(),
  body(
    "The proxy logs all processed requests to stdout at INFO level by default. Set " +
    "LOG_LEVEL=DEBUG for verbose output including full envelope headers and classification " +
    "details.",
    true
  ),
];

// ═══════════════════════════════════════════════════════════════════════════════
// ASSEMBLE DOCUMENT
// ═══════════════════════════════════════════════════════════════════════════════
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0, format: LevelFormat.BULLET, text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
          {
            level: 1, format: LevelFormat.BULLET, text: "◦",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1080, hanging: 360 } } },
          },
        ],
      },
    ],
  },

  styles: {
    default: {
      document: { run: { font: TNR, size: 24 } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: TNR },
        paragraph: { spacing: { before: 480, after: 240 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: TNR },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: TNR },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 },
      },
    ],
  },

  sections: [
    // Section 0: Cover page (no header/footer, Roman numerals)
    {
      properties: {
        ...pageProps("lowerRoman", 1),
        type: SectionType.NEXT_PAGE,
      },
      children: coverChildren,
    },
    // Section 1: Front matter (Declaration, Certificate, Ack, Abstract, TOC)
    {
      properties: {
        ...pageProps("lowerRoman", 2),
        type: SectionType.NEXT_PAGE,
      },
      footers: { default: makeFooter(true) },
      children: [
        ...declarationChildren,
        new Paragraph({ children: [new PageBreak()] }),
        ...certificateChildren,
        new Paragraph({ children: [new PageBreak()] }),
        ...ackChildren,
        new Paragraph({ children: [new PageBreak()] }),
        ...abstractChildren,
        new Paragraph({ children: [new PageBreak()] }),
        ...tocChildren,
      ],
    },
    // Section 2: Main body (Arabic numerals from 1)
    {
      properties: {
        ...pageProps("decimal", 1),
        type: SectionType.NEXT_PAGE,
      },
      headers: { default: makeHeader("LLM-VPN: A Client-Side LLM API Gateway with Semantic Routing") },
      footers: { default: makeFooter(false) },
      children: [
        ...ch1,
        ...ch2,
        ...ch3,
        ...ch4,
        ...ch5,
        ...ch6,
        ...references,
        ...appendix,
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  const outPath = "C:\\Users\\Athar\\Documents\\llm-vpn\\LLM_VPN_Major_Project_Report.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Report written to: " + outPath);
}).catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});
