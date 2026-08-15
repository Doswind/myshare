/**
 * SSE (Server-Sent Events) 流客户端
 *
 * 用 fetch + ReadableStream 解析 SSE 规范：
 *   - 每行以 "data: " 开头
 *   - 事件块以 "\n\n" 分隔
 *   - data: [DONE] 表示流结束
 *
 * 支持 AbortSignal 取消（流中断会触发 onError）。
 */

export interface StreamChatCallbacks {
  onDelta: (event: any) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

export interface StreamChatOptions extends StreamChatCallbacks {
  url: string;
  body: any;
  signal?: AbortSignal;
  /** 默认 'application/json' */
  contentType?: string;
}

/**
 * 流式 POST 到 SSE 端点，逐事件调用 onDelta。
 * 流以 data: [DONE] 结束（调用 onDone）；中途 fetch reject 调 onError。
 */
export async function streamChat(opts: StreamChatOptions): Promise<void> {
  const { url, body, signal, onDelta, onDone, onError, contentType = "application/json" } = opts;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": contentType,
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e: any) {
    onError(new Error(`网络请求失败：${e?.message || e}`));
    return;
  }

  if (!resp.ok || !resp.body) {
    let detail = "";
    try {
      detail = await resp.text();
    } catch {
      /* ignore */
    }
    onError(new Error(`HTTP ${resp.status}${detail ? `：${detail.slice(0, 200)}` : ""}`));
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let done = false;

  try {
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }
      // 按 \n\n 切分事件块；保留最后一段不完整的 buffer
      let splitIdx: number;
      while ((splitIdx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, splitIdx);
        buffer = buffer.slice(splitIdx + 2);
        // 每个 block 可能多行（event:/data:/id: 等），本系统只用 data:
        const lines = block.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;
          if (data === "[DONE]") {
            onDone();
            try {
              await reader.cancel();
            } catch {
              /* ignore */
            }
            return;
          }
          try {
            const parsed = JSON.parse(data);
            onDelta(parsed);
          } catch (e: any) {
            // 非 JSON 不中断流（继续读取），但提示一次
            onError(new Error(`SSE 数据解析失败：${e?.message || e}`));
          }
        }
      }
    }
    // 流自然结束（无 [DONE]）也视为完成
    onDone();
  } catch (e: any) {
    if (e?.name === "AbortError") {
      // 用户主动取消
      return;
    }
    onError(new Error(`SSE 流读取失败：${e?.message || e}`));
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* ignore */
    }
  }
}