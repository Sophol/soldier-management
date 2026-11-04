<script setup>
/**
 * ការងារអត្តសញ្ញាណប័ណ្ណយោធិន (001រចនាសម្ព័ន្ធ): the cards, with why each was made or replaced (មូលហេតុ), those
 * about to expire, and those that still show an old rank or position (ត្រូវធ្វើប័ណ្ណថ្មី). Soldiers without a valid
 * card, or whose card is out of date, open in the soldier list.
 */
import { useRouter } from 'vue-router'
import CrudPage from '@/components/CrudPage.vue'
import { configs } from '@/crud-configs'

const router = useRouter()
const config = configs.idCards
const soldiers = (card) => router.push({ path: '/soldiers', query: { card, serving: 'true' } })
</script>

<template>
  <CrudPage :config="config">
    <template #head-actions>
      <el-button icon="User" @click="soldiers('none')">យោធិនមិនទាន់មានប័ណ្ណ</el-button>
      <el-button icon="Warning" @click="soldiers('outdated')">យោធិនត្រូវធ្វើប័ណ្ណថ្មី</el-button>
    </template>
    <template #cell-outdated_text="{ row }">
      <el-tag v-if="row.outdated?.length" type="warning" size="small">{{ row.outdated_text }}</el-tag>
    </template>
  </CrudPage>
</template>
