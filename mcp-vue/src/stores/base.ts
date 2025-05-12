import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useBaseStore = defineStore('base', () => {
  // 全局加载状态
  const loading = ref(false)
  
  // 设置加载状态
  const setLoading = (status: boolean) => {
    loading.value = status
  }
  
  return {
    loading,
    setLoading
  }
}) 
