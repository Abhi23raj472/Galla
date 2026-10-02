/* Curated Tosca interview questions. Answers are kept short on purpose:
   enough to explain the idea in an interview, with the terms to look up. */
window.TQH_INTERVIEW = [
  // Basics
  { cat: "Basics", q: "What is Tricentis Tosca?",
    a: "A model-based test automation tool for UI, API, mobile and SAP/enterprise apps. Instead of writing scripts, you scan the application into reusable Modules and build TestCases by dragging those Modules in and filling values. It also covers requirements, risk-based test design, test data and execution reporting." },
  { cat: "Basics", q: "What is model-based test automation and why does Tosca use it?",
    a: "The technical description of the app (controls and how to find them) is kept in Modules, separate from the test logic and data in TestCases. When the UI changes you fix the Module once and every TestCase that uses it is updated, which keeps maintenance low compared with script-based tools." },
  { cat: "Basics", q: "Name the main sections of a Tosca workspace.",
    a: "Requirements, TestCaseDesign, Modules, TestCases, Execution and Reporting. Many projects also use Configurations, Reusable TestStepBlocks (Library) and Test Data Management." },
  { cat: "Basics", q: "Single-user vs multi-user workspace?",
    a: "A single-user workspace stores everything locally for one person. A multi-user workspace connects to a shared repository (a database) so a team can work together; objects are checked out to edit and checked in to share, and Update All pulls other people's changes." },
  { cat: "Basics", q: "What is Tosca Commander?",
    a: "The desktop application where you build and manage everything: requirements, Modules, TestCases, ExecutionLists and reports. Newer releases also offer Tosca Cloud with a browser-based UI." },

  // Modules & scanning
  { cat: "Modules & XScan", q: "What is a Module?",
    a: "The technical model of a part of the app under test, such as a login screen. It holds ModuleAttributes (one per control: textbox, button, table) plus the properties Tosca uses to find each control." },
  { cat: "Modules & XScan", q: "What is XScan?",
    a: "The scanner that inspects a running application and creates Modules from the controls you select. You choose the controls, check how they are identified and save them as a Module." },
  { cat: "Modules & XScan", q: "What ways can XScan identify a control?",
    a: "By properties (the default, using technical attributes such as Id, Name or InnerText), by anchor (relative to a stable nearby control), by index (position among similar controls), and by image (visual match, a last resort). Prefer stable unique properties." },
  { cat: "Modules & XScan", q: "Classic engines vs TBox (XModules)?",
    a: "Classic Modules use the older engines. TBox is the newer engine framework; its Modules are XModules with XModuleAttributes and XTestSteps. Most current web, API and SAP work uses TBox engines." },
  { cat: "Modules & XScan", q: "How do you handle dynamic IDs or changing controls?",
    a: "Drop the changing property from identification and use stable ones, use wildcards or partial matches, identify by anchor, or parameterise a property with a business parameter or buffer so the value is supplied at run time." },
  { cat: "Modules & XScan", q: "What is a Tosca table / how do you work with tables?",
    a: "Scan the grid as a table control. In TestSteps you address rows and columns by index, by header or by cell content, e.g. a row whose 'Order No' column equals a buffered value, then act on a cell in that row." },

  // TestCases
  { cat: "TestCases", q: "What are ActionModes?",
    a: "They decide what a TestStepValue does: Input (enter a value or click), Insert (create objects, mostly API), Verify (check a value), Buffer (store a value), WaitOn (wait until a condition is true), Select (pick a control or row to act on), Constraint (narrow which row or object is used) and Exclude (skip)." },
  { cat: "TestCases", q: "Verify vs WaitOn?",
    a: "Verify checks the value once (after normal synchronisation) and fails if it doesn't match. WaitOn keeps checking until the condition is met or the timeout set in the engine settings runs out, which makes it the right tool for slow screens." },
  { cat: "TestCases", q: "What is a buffer and how do you use it?",
    a: "A named run-time variable. Store a value with ActionMode Buffer (or the TBox Set Buffer Module) and read it anywhere with {B[BufferName]}. Common use: capture a generated order number, then search for it later." },
  { cat: "TestCases", q: "Name some dynamic expressions.",
    a: "{B[name]} buffers, {CP[name]} configuration parameters, {DATE} and date arithmetic, {RND[n]} random numbers, {CALC[...]} calculations, and {XL[...]} references used in TestCase Design templates." },
  { cat: "TestCases", q: "What is a Reusable TestStepBlock?",
    a: "A group of TestSteps (e.g. Login) kept in a Library and referenced from many TestCases. Business parameters let each TestCase pass its own values, and changing the block updates every reference." },
  { cat: "TestCases", q: "How do you add conditions and loops?",
    a: "Use If/Else statements and While or Do loops in the TestCase, or set a condition on a TestStep or folder so it only runs when an expression is true. Constraint is used to choose which row or object to act on." },
  { cat: "TestCases", q: "What are configuration parameters?",
    a: "Key/value settings on a TestCase, folder or configuration such as Browser = Chrome or the environment URL. Child objects inherit them and you read them with {CP[name]}, so the same tests can run against different browsers or environments." },

  // Test data & design
  { cat: "Test data & design", q: "What is TestCase Design (TCD)?",
    a: "A section for designing test data and combinations. You build TestSheets with Attributes and Instances (e.g. customer type: new, existing), let Tosca combine them, and link a template TestCase that is instantiated into one TestCase per combination." },
  { cat: "Test data & design", q: "What is a template TestCase and instantiation?",
    a: "A TestCase converted to a template whose values reference TestSheet data with {XL[...]}. Instantiating it generates real TestCases, one per TestSheet instance, and re-instantiating keeps them in sync with the data." },
  { cat: "Test data & design", q: "How does Tosca handle test data management?",
    a: "Static data lives in TestCase Design or configuration parameters. Dynamic data (records consumed by tests) can be kept in Tosca's Test Data Service, where tests find, reserve and update records so parallel runs don't reuse the same data." },
  { cat: "Test data & design", q: "What is risk-based testing in Tosca?",
    a: "Requirements are weighted by how often they are used and how much damage a failure would cause. Linking TestCases to requirements shows risk coverage, so you can prove the riskiest areas are tested first." },

  // Execution
  { cat: "Execution", q: "How do you run tests in Tosca?",
    a: "Add TestCases to an ExecutionList in the Execution section and run it; results are written to ExecutionLogs (the ActualLog shows the latest). You can also run a TestCase directly from the TestCases section with ScratchBook for quick debugging, which isn't kept as a formal result." },
  { cat: "Execution", q: "What is DEX?",
    a: "Distributed Execution: ExecutionLists are sent through Tosca Server to agents on other machines, so tests run in parallel and outside your own desktop. Results flow back into the workspace." },
  { cat: "Execution", q: "What are Recovery and Cleanup scenarios?",
    a: "Recovery scenarios try to bring the app back to a known state after a failure (close a popup, restart) and retry at TestCase, TestStep or TestStepValue level. Cleanup scenarios run when recovery isn't possible so the next TestCase starts cleanly." },
  { cat: "Execution", q: "How do you run Tosca tests from a CI/CD pipeline?",
    a: "Trigger ExecutionLists or event-based runs through Tosca Server's execution API (or the Tosca CI client in older versions) from Jenkins, Azure DevOps, GitLab and so on, then read the JUnit-style results back into the pipeline." },
  { cat: "Execution", q: "How do you find objects quickly in a big workspace?",
    a: "Use TQL (Tosca Query Language) searches, for example finding all TestCases that use a given Module or have failed. Results can be saved as virtual folders that refresh automatically." },

  // API & beyond
  { cat: "API & integrations", q: "How do you do API testing in Tosca?",
    a: "Use the API Scan to import a service from a Swagger/OpenAPI file, WSDL or recorded traffic. It creates API Modules; you build TestCases that send requests, verify responses with Verify, and buffer values (tokens, IDs) for later steps." },
  { cat: "API & integrations", q: "What is Tosca Vision AI?",
    a: "An AI-based engine that recognises controls visually rather than from the technical object tree. It helps with apps that are hard to scan, such as Citrix or remote desktops, or with UIs still in design." },
  { cat: "API & integrations", q: "Which tools does Tosca integrate with?",
    a: "Common ones are Jira and Azure DevOps (requirements and defects), qTest, Jenkins and other CI servers, SAP Solution Manager, and Tosca's own Test Data Service and Server for distributed execution." },
];
