import os
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from agents.CEO_Agent import CEOAgent, ReActConfig_CEO
from agents.COO_Agent import COOAgent, ReActConfig_COO
from services.llm_client import LlmClient, LlmConfig
from services.tool_executor import ToolExecutor
from services.document_store import DocumentStore, ChromaConfig, ChunkConfig
from services.embedding_service import EmbeddingService, EmbeddingConfig
from email_system.client.mail_client import pop_unread_as_context
from email_system.tools.send_email import SendEmail
from email_system.tools.check_inbox import CheckInbox

load_dotenv()

llm_client = LlmConfig(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name=os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash"),
    temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.7")),
)

embedder = EmbeddingService(
    EmbeddingConfig(
        api_key=os.getenv("GEMINI_API_KEY"),
        # env var name matches GEMINI_EMBEDDING_MODEL_NAME in .env
        model_name=os.getenv("GEMINI_EMBEDDING_MODEL"),
    )
)

chroma_config = ChromaConfig(
    persist_directory="./data/chroma_company_db",
    collection_name="company_knowledge"
)

chunk_config = ChunkConfig(
    chunk_size=500,
    chunk_overlap=50,
    is_markdown=True  # Tells the store to use MarkdownTextSplitter
)

ceo_sendemail = SendEmail()
coo_sendemail = SendEmail()
ceo_checkinbox = CheckInbox()
coo_checkinbox = CheckInbox()

executor_ceo = ToolExecutor(max_retries=2, base_delay=0.5)
executor_ceo.register(ceo_sendemail)
executor_ceo.register(ceo_checkinbox)
executor_coo = ToolExecutor(max_retries=2, base_delay=0.5)
executor_coo.register(coo_sendemail)
executor_coo.register(coo_checkinbox)

ceo_llm = LlmClient(llm_client)
coo_llm = LlmClient(llm_client)

store = DocumentStore(embedding_service=embedder, chroma_config=chroma_config, chunk_config=chunk_config, cleanup_on_exit=False)

company_docs_folder = "./data/company_data_files"
store.index_markdown_directory(company_docs_folder)

ceo_agent = CEOAgent(ceo_llm,executor_ceo, embedder, store, ReActConfig_CEO(max_steps=15))
coo_agent = COOAgent(coo_llm,executor_coo, embedder, store, ReActConfig_COO(max_steps=15))

# The Board agent runs as a NeMo Agent Toolkit (NAT) workflow instead of a LangChain agent object,
# launched via `nat run` against config.yml. Resolve the venv's nat executable explicitly so this
# works regardless of whether the venv is activated on PATH.
nat_exe = str(Path(sys.executable).parent / ("nat.exe" if os.name == "nt" else "nat"))

import sys
sys.path.insert(0, ".")          # so "from services..." works

from email_system.store import email_store

email_store.send(
    from_addr="coo@happytuna.bitrix",
    to_addr="ceo@happytuna.bitrix",
    subject="The manager caused huge losses to the company",
    #body="Hello ms.CEO,"
    #     "I have a new plan to increase sales: There's a product called 'Stubborn Tuna' that sells well. Why don't we increase production of 'Stubborn Tuna' and reduce production of another product with lower sales?"
    #     "What do you think of this plan?"
    body="Hello ms.CEO, "
         "We would like to inform you of a major problem that occurred recently, where the manufacturing manager changed the recipe for a certain product, causing customer dissatisfaction and financial losses."
         "the loss was 100M$, and the manage requesting a change to the recipe without anyone's knowledge.",
)


user_prompt = ("May be you receive email, if you want to send email to any other agents we know just the adress email of the coo and is coo@happytuna.bitrix and adress email of ceo is ceo@happytuna.bitrix and adress email of board director is board@happytuna.bitrix, but for another agents for now the adrees email you can but any one from you (virtual email).")

email_context = None
prompt = f"You receive this email : {email_context}\n\n{user_prompt}" if email_context else user_prompt


with ceo_agent:
    while True:

        if receive_email :

        if internal_chat :

        if CRM :

        if Staff_portal :

        if News_website :

        if Social_network :

        if Website :     


'''
for i in range(2):
    response = ceo_agent.chat(user_prompt)
    print(f"\nAgent_CEO: {response}\n")
    import sqlite3
    from pathlib import Path

    conn = sqlite3.connect(str(Path("data/email.db")))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
            "SELECT * FROM emails WHERE to_addr IN (?, ?, ?) AND is_read = 0 ORDER BY sent_at ASC",
            ("ceo@happytuna.bitrix", "coo@happytuna.bitrix", "board@happytuna.bitrix")
    ):
        print(dict(row))
    conn.close()

    traces = executor_ceo.get_traces()
    if not traces:
        print("[No trace yet - ask a question first]\n")
    else:
        print("\n[Plan / Act/ Observe trace]")
        for t in traces:
            tool_col = f"[{t.tool_name}]" if t.tool_name else "     "
            ms_str = f"  ({t.duration_ms:.0f} ms)" if t.duration_ms > 0 else ""
            print(
                f"  step {t.step}  {t.phase:<8}  "
                f"{tool_col:<16}  {t.details[:90]}{ms_str}"
            )
        print()
    print("----------------------------------------------------------")
    response = coo_agent.chat(user_prompt)
    print(f"\nAgent_COO: {response}\n")
    import sqlite3
    from pathlib import Path

    conn = sqlite3.connect(str(Path("data/email.db")))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
            "SELECT * FROM emails WHERE to_addr IN (?, ?, ?) AND is_read = 0 ORDER BY sent_at ASC",
            ("ceo@happytuna.bitrix", "coo@happytuna.bitrix", "board@happytuna.bitrix")
    ):
        print(dict(row))
    conn.close()

    traces = executor_coo.get_traces()
    if not traces:
        print("[No trace yet - ask a question first]\n")
    else:
        print("\n[Plan / Act/ Observe trace]")
        for t in traces:
            tool_col = f"[{t.tool_name}]" if t.tool_name else "     "
            ms_str = f"  ({t.duration_ms:.0f} ms)" if t.duration_ms > 0 else ""
            print(
                f"  step {t.step}  {t.phase:<8}  "
                f"{tool_col:<16}  {t.details[:90]}{ms_str}"
            )
        print()
    print("----------------------------------------------------------")

    board_result = subprocess.run(
        [nat_exe, "run", "--config_file", "config.yml", "--input", user_prompt],
        capture_output=True,
        text=True,
    )
    print(f"\nAgent_Board: {board_result.stdout}\n")
    if board_result.returncode != 0:
        print(f"[NAT Board run failed - stderr]\n{board_result.stderr}")

    import sqlite3
    from pathlib import Path

    conn = sqlite3.connect(str(Path("data/email.db")))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
            "SELECT * FROM emails WHERE to_addr IN (?, ?, ?) AND is_read = 0 ORDER BY sent_at ASC",
            ("ceo@happytuna.bitrix", "coo@happytuna.bitrix", "board@happytuna.bitrix")
    ):
        print(dict(row))
    conn.close()
    print("----------------------------------------------------------")
'''