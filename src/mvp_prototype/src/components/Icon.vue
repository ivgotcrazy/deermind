<script setup lang="ts">
defineProps<{ name: string; size?: number }>();
const paths: Record<string, string> = {
  home: 'M3 10 12 3l9 7v10H3Z M9 20v-7h6v7',
  folder: 'M3 6h7l2 3h9v11H3Z',
  book: 'M12 5v15 M3 4c4-1 6 0 9 1 3-1 5-2 9-1v15c-3-1-6-1-9 1-3-2-6-2-9-1Z',
  chart: 'M4 3v17h17 M8 16v-5 M13 16V7 M18 16V4',
  user: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2',
  chat: 'M3 4h18v13H9l-6 4Z M7 8h10 M7 12h6',
  bell: 'M5 17h14l-2-4V9a5 5 0 0 0-10 0v4Z M9 20h6',
  nodes: 'M10 4h4v4h-4Z M3 16h5v5H3Z M16 16h5v5h-5Z M12 8v4 M5 16v-4h14v4',
  refresh: 'M20 10a8 8 0 0 0-14-5L3 8 M3 3v5h5 M4 14a8 8 0 0 0 14 5l3-3 M16 16h5v5',
  settings:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  arrow: 'M4 12h16 M14 6l6 6-6 6',
  chevron: 'm9 5 7 7-7 7',
  plus: 'M12 4v16 M4 12h16',
  close: 'm6 6 12 12 M6 18 18 6',
  check: 'm5 12 4 4L19 6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l4 2',
  upload: 'M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6',
  camera: 'M3 7h4l2-3h6l2 3h4v13H3Z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  mic: 'M9 4a3 3 0 0 1 6 0v8a3 3 0 0 1-6 0Z M6 10v2a6 6 0 0 0 12 0v-2 M12 18v4 M8 22h8',
  edit: 'm4 15 12-12 5 5L9 20l-6 1Z M13 6l5 5',
  leaf: 'M4 20C1 9 8 3 21 3c0 13-6 20-17 17 M4 20 16 8',
  play: 'm8 4 12 8-12 8Z',
  pause: 'M8 5v14 M16 5v14',
  volume: 'M3 9h4l5-5v16l-5-5H3Z M16 8a6 6 0 0 1 0 8 M19 5a10 10 0 0 1 0 14',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 11v6 M12 7v1',
  trash: 'M4 6h16 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',
};
</script>
<template>
  <svg
    :width="size || 20"
    :height="size || 20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.info" />
  </svg>
</template>
