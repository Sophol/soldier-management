// Large Excel files (soldier list, reports) are made on the server in the background: the request only starts the
// job, this follows it and downloads the file when it is ready. The user may keep working meanwhile (even on another
// page): the download starts by itself.
import { ElMessage, ElNotification } from 'element-plus'
import http, { download } from '@/api/http'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function exportInBackground(url, params, filename) {
  const { data: job } = await http.post(url, null, { params })
  const started = Date.now()
  let note = null
  let failures = 0
  try {
    for (;;) {
      await sleep(Date.now() - started < 10000 ? 1000 : 3000)
      let state
      try {
        state = (await http.get(`/export-jobs/${job.id}`, { silent: true })).data
        failures = 0
      } catch {
        if (++failures >= 10) throw new Error('lost')
        continue
      }
      if (state.status === 'done') {
        await download(`/export-jobs/${job.id}/file`, {}, filename)
        return
      }
      if (state.status === 'failed') {
        ElMessage.error(state.error || 'មិនអាចរៀបចំឯកសារ Excel បានទេ')
        return
      }
      if (!note && Date.now() - started > 4000) {
        note = ElNotification({
          title: 'កំពុងរៀបចំឯកសារ Excel', type: 'info', duration: 0,
          message: `${job.title} — ទិន្នន័យច្រើន អាចប្រើពេលពីរបីនាទី។ អ្នកអាចបន្តធ្វើការងារផ្សេង ឯកសារនឹងទាញយកដោយស្វ័យប្រវត្តិ។`,
        })
      }
    }
  } catch (e) {
    if (e?.message === 'lost') ElMessage.error('បាត់ការតភ្ជាប់ពេលរៀបចំឯកសារ Excel — សូមព្យាយាមម្ដងទៀត')
    else throw e
  } finally {
    note?.close()
  }
}
