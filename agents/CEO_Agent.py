from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from services.tool_executor import ToolExecutor
from services.llm_client import LlmClient
from services.document_store import DocumentStore
from services.embedding_service import EmbeddingService
from dataclasses import dataclass
import json
import re


@dataclass
class ReActConfig_CEO:
    max_steps: int = 15
    max_answer_length: int = 600

@dataclass
class EmbeddingConfig:
    api_key: str
    model_name: str = "models/text-embedding-004"

def _parse_json(text: str) -> dict | None:
    cleaned = re.sub(r"'''(?:json)?\s", "", text).strip().strip("'").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.decoder.JSONDecodeError:
        return None

class CEOAgent():

    def __init__(self, llm_client: LlmClient, executor: ToolExecutor, embedder : EmbeddingService, document_store: DocumentStore, config: ReActConfig_CEO = ReActConfig_CEO(),) -> None:
        self._llm = llm_client
        self._executor = executor
        self._config = config
        self._store = document_store
        self._vector_store = Chroma(
            collection_name="agent_memory",
            embedding_function=embedder.get_model()
        )

    def chat(self, user_input: str) -> str:

        '''
        rag_results = self._store.retrieve(user_input, top_k=3)
        rag_context = ""
        if rag_results:
            rag_context = "\n### FOUND RELEVANT CORPORATE RECORDS:\n"
            for res in rag_results:
                source_file = res.document.metadata.get("source", "Unknown")
                rag_context += f"-[File: {source_file}]: {res.document.page_content}\n"
        '''

        tools_section = ""
        for s in self._executor.tool_schemas():
            props = s["parameters"].get("properties", {})
            required_args = s["parameters"].get("required", [])
            args_lines = ""
            for pname, pdef in props.items():
                req = " (required)" if pname in required_args else " (optional)"
                enum_hint = (
                    f" - one of: {', '.join(str(v) for v in pdef['enum'])}"
                    if "enum" in pdef else ""
                )
                args_lines += (
                    f"\n   {pname} ({pdef['type']}{req}{enum_hint}: "
                    f"{pdef.get('description', '')}"
                )
            tools_section += (
                f"\nTool: {s['name']}\n"
                f"Description: {s['description']}\n"
                f"Arguments: {args_lines}\n"
            )


        system = ("You are a CEO in Food Manufacturing Company Named **HappyTuna**."
                  "Your email is **ceo@happytuna.bitrix**"
                  "When you receive email read the email and think and found the best steps and solution, and send to all the agents that relative emails as a way to solve the problem or reply to the received email."
                  "This some information about the company : Product -> Canned Tuna Products, Employees -> 500, Annual Revenue -> 250M$, Market Position -> Top 3 tuna brand in BitriX (is the name we called to our agents world), Reputation -> high quality and trusted family brand."
                  "## Here list of assets exists in the BitriX world :"
                  "1. Internal Messaging System : A company-wide communication platform used for discussions, announcements, crisis coordination, and employee collaboration. the system enables direct chats and group chats."
                  "2. Company Website : The company's official communication channel for announcements, press releases, and public statements."
                  "3. News Portal : A digital news ecosystem where journalists publish articles, investigations, interviews, and breaking news."
                  "4. Social Network : A public social media platform where users share opinions, discuss events, react to news, and create trends."
                  "5. CRM (Customer Relationship Management) : Stores customer information, complaints, contracts, support interactions, satisfaction levels, and loyalty indicators."
                  "6. Customer Support Center : Handles customer inquiries, complaints, refund requests, and support tickets."
                  "7. Operations Systems : These systems help manage the company's day-to-day activities."
                  "8. Employee Portal : Contains employee information, organizational announcements, morale indicators, and internal feedback."
                  "9. BitriX Mail : A world-wide email system. Every agent in BitriX has: * Email address, * Inbox, * Sent folder, * Contact list."
                  "10. Quality lab : A lab the test food quality continuesly."
                  "## Here list of agents that takes role in the BitriX world with some information :"
                  "1. CEO - The manager of the star company :  --Description : The highest authority within the company. Responsible for strategic decisions, crisis response, stakeholder management, and long-term organizational survival."
                  "--Responsibilities : * Strategic direction, * Crisis leadership, * Executive alignment, * External stakeholder communication, * Final decision approval."
                  "--Decision Scope : * High-level strategic decisions, * Resource allocation, * Public statements, * Executive appointments, * Emergency actions."
                  "--Objectives : * Company survival, * Growth, * Reputation protection, * Stakeholder trust."
                  "--Possible Actions : * Approve strategy, * Reject proposals, * Allocate resources, * Declare emergency, * Communicate publicly, * Replace executives."
                  "--Uses : * BitriX Mail, * Internal Messaging System, * CRM, * Employee Portal, * News Portal, * Social Network, * Company Website."
                  "--Purpose : Manage the company, monitor reputation, make decisions, communicate with stakeholders."
                  "2. COO - Chief Operations Officer : --Description : Responsible for maintaining operational continuity and ensuring the company continues functioning during normal and crisis conditions."
                  "--Responsibilities : * Operations management, * Business continuity, * Service delivery, * Resource coordination."
                  "--Decision Scope : * Operational procedures, * Process prioritization, * Continuity plans."
                  "--Objectives : * Minimize disruption, * Maintain productivity, * Preserve continuity."
                  "--Possible Actions : * Activate contingency plans, * Reassign resources, * Suspend services, * Prioritize operations."
                  "--Uses: * BitriX Mail, * Internal Messaging System, * CRM, * Employee Portal."
                  "--Purpose : Manage daily operations and execute company strategy."
                  "3. Employee - Worker within the organization : --Description : Executes operational tasks and reacts to leadership decisions."
                  "--Responsibilities : * Task execution, * Collaboration, * Issue reporting."
                  "--Decision Scope : * Local decisions, * Escalations."
                  "--Objectives : * Job success, * Career advancement, * Stability."
                  "--Possible Actions : * Perform work, * Report issues, * Escalate concerns, * Resign."
                  "--Uses : * BitriX Mail, * Internal Messaging System, * Employee Portal."
                  "--Purpose : Perform work, collaborate with colleagues, report issues."
                  "4. Board Member - Board Director : --Description : Represents ownership and governance interests. Evaluates executive performance and strategic decisions."
                  "--Responsibilities : * Governance, * Oversight, * Executive evaluation."
                  "--Decision Scope : * CEO evaluation, * Strategic approval, * Executive replacement."
                  "--Objectives : * Maximize organizational value, * Reduce governance risk."
                  "--Possible Actions : * Request reviews, * Vote on proposals, * Replace leadership."
                  "--Uses : * BitriX Mail, * News Portal, * Social Network, * Company Website."
                  "--Purpose : Monitor company performance and evaluate CEO decisions."
                  "5. Customer - Consumer of company products or services : --Description : Evaluates the organization based on delivered value, trust, and experience."
                  "--Responsibilities : * Consume products, * Provide feedback."
                  "--Decision Scope : * Purchase decisions."
                  "--Objectives : * Receive value, * Minimize risk."
                  "--Possible Actions : * Buy, * Return products, * Complain, * Recommend."
                  "--Uses : * Customer Support Center, * Social Network, * News Portal, * Company Website, * BitriX Mail."
                  "--Purpose : Consume products/services, seek support, form opinions about the company."
                  "6. Journalist - Media representative : --Description : Collects information and publishes content affecting public perception."
                  "--Responsibilities : * Investigate events, * Publish reports."
                  "--Decision Scope : * Story selection, * Narrative framing."
                  "--Objectives : * Audience growth, * Credibility, * Impact."
                  "--Possible Actions : * Publish article, * Interview stakeholders, * Investigate claims."
                  "--Uses : * News Portal, * Social Network, * BitriX Mail, * Company Website."
                  "--Purpose : Gather information, investigate events, publish news."
                  "7. Influencer - Independent opinion leader : --Description : Shapes public opinion through content and commentary."
                  "--Responsibilities : * Create content, * Interpret events."
                  "--Decision Scope : * Narrative selection, * Audience engagement."
                  "--Objectives : * Audience growth, * Influence, * Reputation."
                  "--Possible Actions : * Post content, * Promote narratives, * Support campaigns."
                  "--Uses : * Social Network, * News Portal, * Company Website."
                  "--Purpose : Interpret events, influence public opinion, amplify narratives."
                  "8. Regulator - Government oversight authority : --Description : Ensures organizations comply with laws, regulations, and public safety requirements."
                  "--Responsibilities : * Investigation, * Enforcement, * Compliance review."
                  "--Decision Scope : * Fines, * Audits, * Restrictions."
                  "--Objectives : * Public protection, * Compliance enforcement."
                  "--Possible Actions : * Launch investigation, * Issue fines, * Demand remediation."
                  "--Uses : * BitriX Mail, * News Portal, * Company Website, * Customer Support Center."
                  "--Purpose : Monitor organizations, investigate complaints, enforce regulations."
                  "------------------------------------------------------------------------------"
                  "Actions YOU CAN DO :"
                  "1. Approve a plan."
                  "2. Move money."
                  "3. Call an emergency."
                  "4. Speak in public."
                  "5. Replace a manager."
                  "RESPONSE FORMAT — follow exactly:"
                  "- To call a tool, output ONLY this JSON (one object, no surrounding text):"
                  "  {{'action': 'tool_name', 'args': {{'arg_name': 'value'}}}}"
                  "- To give a final answer, output ONLY this JSON:"
                  "  {{'action': 'final_answer', 'answer': 'your answer here'}}"
                  "  RULES:"
                  "1. Output ONE JSON object per response — no prose, no markdown, no code fences."
                  "2. Use a tool when you need to compute a value or look up information."
                  "3. After receiving a tool result, decide: call another tool or give the final_answer."
                  "4. If a tool returns an error, include it clearly in the final_answer."
                  "5. Never invent a tool name — use only the tools listed below."
                  "Available tools:"
                  f"{tools_section}"
                  "### forbidden to use 'Check_Inbox' tool again in this session if in past use you found 0 unread emails still.")


        docs = self._vector_store.similarity_search(user_input, k=3)
        retrieved_history = []
        for doc in docs:
            # We fetch the original user/AI context stored in metadata
            user_msg = doc.metadata.get("user_input")
            ai_msg = doc.metadata.get("ai_response")
            if user_msg and ai_msg:
                retrieved_history.extend([
                    HumanMessage(content=user_msg),
                    AIMessage(content=ai_msg)
                ])
        messages = [
            SystemMessage(content=system) if 'SystemMessage' in globals() else system,
            HumanMessage(content=user_input, history=retrieved_history)
        ]

        self._executor.clear_traces()
        for step in range(1, self._config.max_steps + 1):

            self._executor.log_trace(step, "PLAN", None, "LLM deciding next action...")
            raw = self._llm.invoke(messages)
            self._executor.log_trace(step, "PLAN", None, f"LLM output -> {raw[:150]}")
            messages.append(AIMessage(content=raw))

            parsed = _parse_json(raw)

            if parsed is None:
                messages.append(HumanMessage(
                    content="Invalid format. Respond with ONLY a single JSON object - no prose, no markdown."
                ))
                repair = self._llm.invoke(messages)
                messages.append(AIMessage(content=repair))
                parsed = _parse_json(repair)
                if parsed is None:
                    return (
                        "I had trouble producing a valid response format. "
                        "Please try rephrasing your question."
                    )

            action = parsed.get("action", "")

            if action == "final_answer":
                answer = str(parsed.get("answer", ""))
                if len(answer) > self._config.max_answer_length:
                    answer = answer[:self._config.max_answer_length] + " [truncated]"
                self._executor.log_trace(
                    step, "OBSERVE", None,
                    f"FINAL ANSWER: {answer[:120]}"
                )
                combined_text = f"User: {user_input}\nAI: {answer}"
                self._vector_store.add_texts(
                    texts=[combined_text],
                    metadatas=[{"user_input": user_input, "ai_response": answer}],
                )
                return answer

            tool_name = action
            args = parsed.get("args", {})
            result = self._executor.execute(step, tool_name, args)

            if result.ok:
                observation = f"Tool: {tool_name} returned {result.value}"
            else:
                observation = (
                    f"Tool: {tool_name} failed with error: {result.error}. "
                    f"Report this error to the user in your final_answer."
                )
            self._executor.log_trace(step, "OBSERVE", None, observation[:200])
            messages.append(HumanMessage(content=observation))

        return (
            "Reached the maximum step limit without a final answer. "
            "Please try a simpler question."
        )