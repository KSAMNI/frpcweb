<script setup lang="ts">
import { NSelect } from 'naive-ui'
import { groupOptions } from '../api'
withDefaults(
  defineProps<{
    modelValue: string
    label?: string
    disabled?: boolean
    size?: 'small' | 'medium'
  }>(),
  { label: '分组', disabled: false, size: 'medium' },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
function update(value: unknown) {
  emit('update:modelValue', typeof value === 'string' ? value.trim() : '')
}
</script>

<template>
  <NSelect
    :value="modelValue"
    :options="groupOptions"
    :disabled="disabled"
    :size="size"
    :input-props="{ 'aria-label': label, maxlength: 50 }"
    :aria-label="label"
    filterable
    tag
    clearable
    placeholder="选择或输入新分组"
    @update:value="update"
  />
</template>
