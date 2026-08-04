import { useState, type ReactNode } from "react";
import {
  CalendarCheck,
  CheckCircle,
  ClipboardText,
  FileMagnifyingGlass,
  ListChecks,
  NotePencil,
  PaperPlaneTilt,
  Play,
  Sparkle,
  UploadSimple,
  WarningCircle
} from "@phosphor-icons/react";
import { runTradeChat, uploadTradeDocument, type ApiStatus, type TradeChatResult } from "./api";
import { demoResult, sampleQuestion } from "./demo";

const taskPresets = [
  "合同检查",
  "结算核对",
  "周报草稿",
  "资料问答"
];

function App() {
  const [question, setQuestion] = useState(sampleQuestion);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<ApiStatus>("idle");
  const [uploadMessage, setUploadMessage] = useState("");
  const [taskPreset, setTaskPreset] = useState(taskPresets[0]);
  const [status, setStatus] = useState<ApiStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<TradeChatResult>(demoResult);

  const evidence = result.evidence ?? [];
  const sources = result.sources ?? [];
  const nextSteps = result.next_steps ?? [];

  async function handleRun() {
    setStatus("loading");
    setError("");
    try {
      const response = await runTradeChat({
        user_input: `${taskPreset}：${question}`,
        tenant_id: "company_internal",
        user_id: "business_user",
        department_ids: ["business"],
        clearance_level: "internal",
        max_cost_units: 10
      });
      setResult(response);
      setStatus("success");
    } catch (caught) {
      setResult(demoResult);
      setError(caught instanceof Error ? caught.message : "服务暂不可用，请稍后重试。");
      setStatus("error");
    }
  }

  async function handleUpload() {
    if (!documentFile) {
      setUploadStatus("error");
      setUploadMessage("请先选择要入库的业务资料文件。");
      return;
    }

    setUploadStatus("loading");
    setUploadMessage("");
    try {
      const response = await uploadTradeDocument(documentFile);
      const indexed = response.index_stats?.indexed_files ?? 0;
      const skipped = response.index_stats?.skipped_files ?? 0;
      setUploadStatus("success");
      setUploadMessage(`已上传 ${response.file_name}，索引新增 ${indexed} 个文件，跳过 ${skipped} 个未变化文件。`);
    } catch (caught) {
      setUploadStatus("error");
      setUploadMessage(caught instanceof Error ? caught.message : "资料上传或入库失败。");
    }
  }

  return (
    <main className="businessShell compactShell">
      <section className="businessOverview" aria-label="业务概览">
        <article>
          <small>常用场景</small>
          <strong>合同检查</strong>
          <p>核对主体、金额、付款节点和附件。</p>
        </article>
        <article>
          <small>处理方式</small>
          <strong>先出草稿</strong>
          <p>把问题整理成可继续跟进的意见。</p>
        </article>
        <article>
          <small>复核重点</small>
          <strong>人工确认</strong>
          <p>关键字段保留给业务员最后判断。</p>
        </article>
      </section>

      <section className="workspace">
        <div className="composePanel">
          <div className="panelHead">
            <NotePencil size={22} />
            <div>
              <h2>需要我帮您做什么</h2>
              <p>描述要处理的合同、结算、资料或汇报任务。</p>
            </div>
          </div>

          <div className="presetGrid" aria-label="业务场景">
            {taskPresets.map((preset) => (
              <button
                className={preset === taskPreset ? "preset active" : "preset"}
                key={preset}
                type="button"
                onClick={() => setTaskPreset(preset)}
              >
                {preset}
              </button>
            ))}
          </div>

          <label>
            <span>上传业务资料</span>
            <input
              accept=".txt,.docx,.pdf,.xlsx,.jpg,.jpeg,.png"
              type="file"
              onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="secondaryAction" type="button" onClick={handleUpload} disabled={uploadStatus === "loading"}>
            {uploadStatus === "loading" ? <Sparkle size={18} weight="duotone" /> : <UploadSimple size={18} weight="bold" />}
            {uploadStatus === "loading" ? "正在上传入库" : "上传资料并更新索引"}
          </button>
          {documentFile ? <p className="inlineStatus">待入库：{documentFile.name}</p> : null}
          {uploadMessage ? <p className={`formMessage ${uploadStatus}`}>{uploadMessage}</p> : null}

          <label>
            <span>业务问题</span>
            <textarea value={question} rows={12} onChange={(event) => setQuestion(event.target.value)} />
          </label>

          <button className="primaryAction" type="button" onClick={handleRun} disabled={status === "loading"}>
            {status === "loading" ? <Sparkle size={18} weight="duotone" /> : <Play size={18} weight="fill" />}
            {status === "loading" ? "正在整理处理意见" : "整理处理意见"}
          </button>
        </div>

        <div className="resultPanel">
          <article className="answerCard">
            <div className="cardTitle">
              <PaperPlaneTilt size={22} />
              <h2>处理意见</h2>
            </div>
            <p>{result.final_answer ?? "提交问题后显示处理意见。"}</p>
          </article>

          <div className="businessCards">
            <InfoCard
              icon={<WarningCircle size={22} />}
              title="需要确认"
              items={nextSteps.length ? nextSteps : ["核对金额、主体、日期和附件完整性"]}
            />
            <InfoCard
              icon={<FileMagnifyingGlass size={22} />}
              title="参考材料"
              items={sources.length ? sources.map(formatSource) : ["等待助手返回参考资料"]}
            />
            <InfoCard
              icon={<ListChecks size={22} />}
              title="可执行下一步"
              items={evidence.length ? evidence : ["等待助手返回处理依据"]}
            />
          </div>
        </div>
      </section>

      <section className="handoffBand">
        <Handoff icon={<CalendarCheck size={22} />} title="少漏关键字段" text="合同主体、金额、付款节点和附件会被集中列出。" />
        <Handoff icon={<CheckCircle size={22} />} title="答复能追溯" text="每次处理意见都保留参考材料和人工确认项。" />
      </section>
    </main>
  );
}

function InfoCard({ icon, title, items }: { icon: ReactNode; title: string; items: string[] }) {
  return (
    <article className="infoCard">
      <div className="cardTitle small">
        {icon}
        <h3>{title}</h3>
      </div>
      <div className="itemList">
        {items.slice(0, 4).map((item) => <p key={item}>{item}</p>)}
      </div>
    </article>
  );
}

function Handoff({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <article className="handoff">
      {icon}
      <strong>{title}</strong>
      <p>{text}</p>
    </article>
  );
}

function formatSource(source: Record<string, unknown>) {
  return String(source.file ?? "业务资料片段");
}

export default App;
