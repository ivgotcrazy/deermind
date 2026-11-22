<script setup lang="ts">
import type { DataTable } from './types';

defineProps<{ table: DataTable; caption: string }>();

const cellLabels = {
  response_blank: '待填写',
  source_missing: '原文未提供',
  unreadable: '识别不清',
};

function cellText(cell: DataTable['rows'][number]['cells'][string] | undefined) {
  if (!cell) return '原文未提供';
  return cell.state === 'provided' ? cell.value : cellLabels[cell.state];
}
</script>

<template>
  <div class="table-scroll" role="region" :aria-label="caption || '数据表'" tabindex="0">
    <table>
      <caption v-if="caption">
        {{
          caption
        }}
      </caption>
      <thead>
        <tr>
          <th v-for="column in table.columns" :key="column.key" scope="col">
            {{ column.label }}<span v-if="column.unit">（{{ column.unit }}）</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in table.rows" :key="row.row_id">
          <td
            v-for="column in table.columns"
            :key="column.key"
            :class="{
              numeric: column.value_type === 'decimal',
              missing: row.cells[column.key]?.state !== 'provided',
            }"
          >
            {{ cellText(row.cells[column.key]) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-scroll {
  overflow-x: auto;
}

.table-scroll:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

caption {
  margin-bottom: 0.375rem;
  font-weight: 600;
  text-align: left;
}

th,
td {
  padding: 0.5rem 0.625rem;
  border-bottom: 1px solid var(--color-line);
  text-align: left;
  vertical-align: top;
}

th {
  background: #edf2ed;
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.missing {
  color: var(--color-muted);
  font-size: 0.85em;
}
</style>
