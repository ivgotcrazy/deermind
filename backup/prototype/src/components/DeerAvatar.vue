<script setup lang="ts">
/* 小鹿虚拟形象（SVG，无外链图片） */
const props = defineProps<{ size?: number }>()
const s = props.size ?? 56
</script>

<template>
  <svg :width="s" :height="s" viewBox="0 0 96 96" aria-hidden="true">
    <!-- 耳朵 -->
    <ellipse cx="30" cy="26" rx="12" ry="16" fill="#F6C9A0" transform="rotate(-18 30 26)" />
    <ellipse cx="66" cy="26" rx="12" ry="16" fill="#F6C9A0" transform="rotate(18 66 26)" />
    <ellipse cx="31" cy="28" rx="6" ry="9" fill="#F4A6B8" transform="rotate(-18 31 28)" />
    <ellipse cx="65" cy="28" rx="6" ry="9" fill="#F4A6B8" transform="rotate(18 65 28)" />
    <!-- 鹿角 -->
    <g stroke="#B98A5A" stroke-width="5" stroke-linecap="round" fill="none">
      <path d="M34 30 C28 20 22 22 24 14" />
      <path d="M32 26 C36 20 34 14 40 12" />
      <path d="M62 30 C68 20 74 22 72 14" />
      <path d="M64 26 C60 20 62 14 56 12" />
    </g>
    <!-- 脸 -->
    <ellipse cx="48" cy="52" rx="32" ry="30" fill="#F6C9A0" />
    <!-- 腮红 -->
    <ellipse cx="30" cy="62" rx="8" ry="6" fill="#F4A6B8" opacity="0.6" />
    <ellipse cx="66" cy="62" rx="8" ry="6" fill="#F4A6B8" opacity="0.6" />
    <!-- 眼睛 -->
    <circle cx="39" cy="50" r="5" fill="#3A2E24" />
    <circle cx="57" cy="50" r="5" fill="#3A2E24" />
    <circle cx="41" cy="48" r="1.8" fill="#fff" />
    <circle cx="59" cy="48" r="1.8" fill="#fff" />
    <!-- 鼻子 -->
    <ellipse cx="48" cy="58" rx="3" ry="2.4" fill="#3A2E24" />
    <!-- 嘴（微笑） -->
    <path d="M42 64 Q48 70 54 64" stroke="#3A2E24" stroke-width="2.5" fill="none" stroke-linecap="round" />
  </svg>
</template>
