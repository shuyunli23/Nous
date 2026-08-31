import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Type } from 'lucide-react';

export const LYRIC_FONTS = [
  {
    id: 'sans',
    name: '黑体',
    family: '"Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif',
  },
  {
    id: 'serif',
    name: '宋体',
    family: '"Noto Serif SC", "Songti SC", SimSun, serif',
  },
  {
    id: 'round',
    name: '圆体',
    family: '"ZCOOL QingKe HuangYou", "Yuanti SC", sans-serif',
    lineScale: 1.08,
  },
  {
    id: 'display',
    name: '海报',
    family: '"ZCOOL XiaoWei", "Noto Serif SC", serif',
    lineScale: 1.1,
  },
  {
    id: 'hand',
    name: '手写',
    family: '"Ma Shan Zheng", "KaiTi", cursive',
    lineScale: 1.18,
  },
];

export function fontById(id) {
  return LYRIC_FONTS.find((item) => item.id === id) || LYRIC_FONTS[0];
}

export function FontSelector({ current, onChange }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative z-[60]">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="p-2 rounded-full hover:bg-white/10 transition-colors"
        title="Switch lyric font"
      >
        <Type className="w-5 h-5 sm:w-6 sm:h-6" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-[60]"
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(false);
            }}
          />
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="absolute top-full mt-2 right-0 z-[70] bg-zinc-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl py-2 min-w-[176px] max-h-[70vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {LYRIC_FONTS.map((font) => {
              const active = current === font.id;
              return (
                <button
                  key={font.id}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(font.id);
                    setIsOpen(false);
                  }}
                  className={`w-full px-4 py-2.5 text-left text-[15px] transition-colors ${
                    active
                      ? 'text-emerald-400 bg-emerald-500/10'
                      : 'text-zinc-300 hover:bg-white/5 hover:text-white'
                  }`}
                  style={{ fontFamily: font.family }}
                >
                  <span className="flex items-center gap-2">
                    {active ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    ) : (
                      <span className="w-1.5" />
                    )}
                    <span>{font.name}</span>
                    <span className="ml-auto text-xs opacity-45">烟花易冷</span>
                  </span>
                </button>
              );
            })}
          </motion.div>
        </>
      )}
    </div>
  );
}
