<script setup>
import { computed } from 'vue'
import CrudPage from '@/components/CrudPage.vue'
import { configs } from '@/crud-configs'

const props = defineProps({ name: { type: String, required: true } })
const config = computed(() => configs[props.name])
</script>

<template>
  <CrudPage :config="config" />
</template>
