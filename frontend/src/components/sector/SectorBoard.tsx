import { useState } from "react";
import type { SectorGroup } from "@/types/api";
import { SectorCard } from "./SectorCard";
import { SectorAllStocksModal } from "./SectorAllStocksModal";
import { GripVertical } from "lucide-react";

interface SectorBoardProps {
  sectors: SectorGroup[];
  loading?: boolean;
  reportDate?: string;
  onStockClick?: (code: string) => void;
  onSectorClick?: (sector: SectorGroup) => void;
}

export function SectorBoard({ sectors, loading, reportDate, onStockClick, onSectorClick }: SectorBoardProps) {
  const [order, setOrder] = useState<string[]>([]);
  const [dragged, setDragged] = useState<string | null>(null);
  const [activeSector, setActiveSector] = useState<SectorGroup | null>(null);

  // 同步 sectors 顺序
  const currentOrder = order.length === sectors.length
    ? order
    : sectors.map((s) => s.industry_name);
  const byName = Object.fromEntries(sectors.map((s) => [s.industry_name, s]));
  const ordered = currentOrder.map((n) => byName[n]).filter(Boolean);

  const handleDragStart = (e: React.DragEvent, name: string) => {
    setDragged(name);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (e: React.DragEvent, target: string) => {
    e.preventDefault();
    if (!dragged || dragged === target) return;
    const newOrder = [...currentOrder];
    const fromIdx = newOrder.indexOf(dragged);
    const toIdx = newOrder.indexOf(target);
    if (fromIdx === -1 || toIdx === -1) return;
    newOrder.splice(fromIdx, 1);
    newOrder.splice(toIdx, 0, dragged);
    setOrder(newOrder);
    setDragged(null);
  };

  if (loading && sectors.length === 0) {
    return (
      <div className="text-center text-slate-400 py-10 text-[12px]">加载中…</div>
    );
  }

  if (!loading && sectors.length === 0) {
    return (
      <div className="text-center text-slate-400 py-10 text-[12px]">
        暂无符合条件的股票，请降低筛选条件或等待数据抓取
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
        {ordered.map((s) => (
          <div
            key={s.industry_name}
            draggable
            onDragStart={(e) => handleDragStart(e, s.industry_name)}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, s.industry_name)}
            onDragEnd={() => setDragged(null)}
            className="relative group"
          >
            <GripVertical className="absolute -left-1 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-300 opacity-0 group-hover:opacity-100 cursor-move" />
            <SectorCard
              sector={s}
              dragging={dragged === s.industry_name}
              onSectorClick={() => onSectorClick?.(s)}
              onStockClick={onStockClick}
              onShowAllStocks={() => setActiveSector(s)}
            />
          </div>
        ))}
      </div>
      <SectorAllStocksModal
        sector={activeSector}
        reportDate={reportDate}
        onClose={() => setActiveSector(null)}
        onStockClick={(code) => {
          setActiveSector(null);
          onStockClick?.(code);
        }}
      />
    </>
  );
}
