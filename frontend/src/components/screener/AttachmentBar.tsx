import { useRef } from "react";
import { Paperclip, X, FileText, Image as ImageIcon } from "lucide-react";
import type { ChatAttachment } from "@/api/openclaw";

/** 附件限制 */
export const IMG_MAX = 10 * 1024 * 1024; // 10MB
export const FILE_MAX = 5 * 1024 * 1024; // 5MB
export const MAX_COUNT = 5;

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif"];
const FILE_TYPES = [
  "text/plain",
  "text/markdown",
  "text/html",
  "text/csv",
  "application/json",
  "application/pdf",
];

export interface LocalAttachment extends ChatAttachment {
  /** 图片预览 data URL（仅前端展示用，不发送） */
  preview?: string;
}

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = reader.result as string;
      // data:<mime>;base64,<data> → 取逗号后
      const idx = res.indexOf(",");
      resolve(idx >= 0 ? res.slice(idx + 1) : res);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** 把 File 列表转成附件，返回 {added, errors} */
export async function filesToAttachments(
  files: File[],
  existing: LocalAttachment[],
): Promise<{ added: LocalAttachment[]; errors: string[] }> {
  const added: LocalAttachment[] = [];
  const errors: string[] = [];
  let count = existing.length;

  for (const file of files) {
    if (count >= MAX_COUNT) {
      errors.push(`最多上传 ${MAX_COUNT} 个附件`);
      break;
    }
    const isImage = IMAGE_TYPES.includes(file.type);
    const isFile = FILE_TYPES.includes(file.type);
    if (!isImage && !isFile) {
      errors.push(`不支持的类型：${file.name}`);
      continue;
    }
    if (isImage && file.size > IMG_MAX) {
      errors.push(`图片超过 10MB：${file.name}`);
      continue;
    }
    if (isFile && file.size > FILE_MAX) {
      errors.push(`文件超过 5MB：${file.name}`);
      continue;
    }
    try {
      const data = await readAsBase64(file);
      const att: LocalAttachment = {
        name: file.name,
        media_type: file.type,
        kind: isImage ? "image" : "file",
        data,
      };
      if (isImage) att.preview = `data:${file.type};base64,${data}`;
      added.push(att);
      count++;
    } catch {
      errors.push(`读取失败：${file.name}`);
    }
  }
  return { added, errors };
}

interface Props {
  value: LocalAttachment[];
  onChange: (next: LocalAttachment[]) => void;
  onError?: (msg: string) => void;
  disabled?: boolean;
}

export function AttachmentBar({ value, onChange, onError, disabled }: Props) {
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleFiles(files: FileList | File[]) {
    const arr = Array.from(files);
    if (!arr.length) return;
    const { added, errors } = await filesToAttachments(arr, value);
    if (added.length) onChange([...value, ...added]);
    if (errors.length && onError) onError(errors.join("；"));
  }

  function remove(idx: number) {
    onChange(value.filter((_, i) => i !== idx));
  }

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => imageInputRef.current?.click()}
        className="flex items-center justify-center w-7 h-7 rounded-md text-slate-500 hover:bg-slate-100 disabled:opacity-40"
        title="上传图片（jpg/png/gif/webp，≤10MB）"
      >
        <ImageIcon className="w-4 h-4" />
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => fileInputRef.current?.click()}
        className="flex items-center justify-center w-7 h-7 rounded-md text-slate-500 hover:bg-slate-100 disabled:opacity-40"
        title="上传附件（txt/md/csv/json/pdf 等，≤5MB）"
      >
        <Paperclip className="w-4 h-4" />
      </button>
      <input
        ref={imageInputRef}
        type="file"
        multiple
        accept={IMAGE_TYPES.join(",")}
        className="hidden"
        onChange={(e) => {
          if (e.target.files) handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={FILE_TYPES.join(",")}
        className="hidden"
        onChange={(e) => {
          if (e.target.files) handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 w-full mt-1.5">
          {value.map((att, i) => (
            <div
              key={att.name + i}
              className="flex items-center gap-1 rounded border border-slate-200 bg-slate-50 pl-1 pr-1.5 py-0.5 text-[11px] text-slate-600 max-w-[160px]"
            >
              {att.preview ? (
                <img src={att.preview} alt="" className="w-5 h-5 rounded object-cover" />
              ) : att.kind === "image" ? (
                <ImageIcon className="w-3.5 h-3.5 text-slate-400" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span className="truncate">{att.name}</span>
              <button
                type="button"
                onClick={() => remove(i)}
                className="text-slate-400 hover:text-red-500 shrink-0"
                title="移除附件"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
