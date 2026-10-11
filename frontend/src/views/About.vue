<script setup>
import { onMounted, ref } from 'vue'
import http from '@/api/http'

const settings = ref({})
onMounted(async () => { settings.value = (await http.get('/settings')).data })
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>អំពីយើង</h2></div>
    <el-card shadow="never">
      <div class="about">
        <img src="/favicon.svg" alt="" />
        <div>
          <h3 class="moul">ប្រព័ន្ធគ្រប់គ្រងយោធិន</h3>
          <p>{{ settings.org_name_kh?.value }}</p>
          <p class="muted">{{ settings.org_name_en?.value }}</p>
          <p>
            ប្រព័ន្ធនេះប្រើសម្រាប់គ្រប់គ្រងប្រវត្តិរូបយោធិន ឯកសារចេញចូល ការតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ
            ការបណ្ដុះបណ្ដាល វិន័យ ការសរសើរ សោធននិវត្តន៍ យោធិនចេញពីជួរ និងរបាយការណ៍។
          </p>
          <el-descriptions :column="1" border size="small" style="max-width: 460px">
            <el-descriptions-item label="កំណែ">1.0.0</el-descriptions-item>
            <el-descriptions-item label="Backend">Python · FastAPI · SQLAlchemy</el-descriptions-item>
            <el-descriptions-item label="Frontend">Vue 3 · Element Plus</el-descriptions-item>
            <el-descriptions-item label="Database">MySQL</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.about { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; }
.about img { width: 96px; }
h3 { color: var(--brand); margin-top: 0; line-height: 1.8; }
p { line-height: 1.9; max-width: 720px; }
</style>
