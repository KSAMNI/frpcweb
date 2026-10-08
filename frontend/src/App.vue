<script setup lang="ts">
import {
  zhCN,
  dateZhCN,
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  type GlobalThemeOverrides,
} from 'naive-ui'
import AppShell from './components/AppShell.vue'
const theme: GlobalThemeOverrides = {
  common: {
    primaryColor: '#128579',
    primaryColorHover: '#0d7268',
    primaryColorPressed: '#096258',
    borderRadius: '8px',
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif',
    textColorBase: '#263449',
    fontSize: '14px',
  },
  Button: { fontWeight: '500' },
  DataTable: { thColor: '#f7f9fc', thTextColor: '#758196', borderColor: '#edf0f4' },
}
</script>

<template>
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="theme">
    <NMessageProvider>
      <NDialogProvider><AppShell /></NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
