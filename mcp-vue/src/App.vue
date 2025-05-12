<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { initTheme } from './utils/theme'
import { onMounted } from 'vue'

// 初始化主题
onMounted(() => {
  initTheme()
})
</script>

<style>
:root {
  /* 这些变量会被主题系统动态更新 */
  --mcp-bgPrimary: #1A1A1A;
  --mcp-bgSecondary: #2C2C2C;
  --mcp-bgTertiary: #3C3C3C;
  --mcp-textPrimary: #FFFFFF;
  --mcp-textSecondary: #888888;
  --mcp-borderPrimary: #2C2C2C;
  --mcp-borderSecondary: #3C3C3C;
  --mcp-primary: #D32F2F;
  --mcp-primaryHover: #B71C1C;
  --mcp-success: #4CAF50;
  --mcp-warning: #FFA726;
  --mcp-danger: #D32F2F;
  --mcp-info: #888888;
  --mcp-primary-rgb: 211, 47, 47; /* 红色主题 */
}

/* 基础样式 */
body {
  margin: 0;
  background-color: var(--mcp-bgPrimary);
  color: var(--mcp-textPrimary);
  padding: 0;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

#app {
  height: 100vh;
  background-color: var(--mcp-bgPrimary);
  width: 100vw;
  overflow: hidden;
}

/* Element Plus 样式覆盖 */
.el-button--primary {
  background-color: var(--mcp-primary) !important;
  border-color: var(--mcp-primary) !important;
}

.el-button--primary:hover,
.el-button--primary:focus {
  background-color: var(--mcp-primaryHover) !important;
  border-color: var(--mcp-primaryHover) !important;
}

.el-button--default {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
  color: var(--mcp-textPrimary) !important;
}

.el-button--default:hover,
.el-button--default:focus {
  border-color: var(--mcp-primary) !important;
}

/* 确保对话框内的按钮也使用主题变量 */
.el-dialog .el-button--primary {
  background-color: var(--mcp-primary) !important;
  border-color: var(--mcp-primary) !important;
}

.el-dialog .el-button--primary:hover,
.el-dialog .el-button--primary:focus {
  background-color: var(--mcp-primaryHover) !important;
  border-color: var(--mcp-primaryHover) !important;
}

.el-dialog .el-button--default {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
  color: var(--mcp-textPrimary) !important;
}

.el-dialog .el-button--default:hover,
.el-dialog .el-button--default:focus {
  border-color: var(--mcp-primary) !important;
}

.el-input__wrapper {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderPrimary) !important;
}

.el-input__inner {
  color: var(--mcp-textPrimary) !important;
}

/* 对话框样式增强 */
.el-dialog {
  background-color: var(--mcp-bgPrimary) !important;
  border: 1px solid var(--mcp-borderPrimary) !important;
}

.el-dialog__header {
  background-color: var(--mcp-bgPrimary) !important;
  border-bottom: 1px solid var(--mcp-borderPrimary) !important;
  margin-right: 0 !important;
  padding: 20px 24px !important;
}

.el-dialog__title {
  color: var(--mcp-textPrimary) !important;
  font-size: 1.2rem !important;
  font-weight: 500 !important;
}

.el-dialog__headerbtn {
  top: 20px !important;
  right: 20px !important;
}

.el-dialog__headerbtn:hover .el-dialog__close {
  color: var(--mcp-primary) !important;
}

.el-dialog__body {
  background-color: var(--mcp-bgPrimary) !important;
  color: var(--mcp-textPrimary) !important;
  padding: 24px !important;
}

.el-dialog__footer {
  background-color: var(--mcp-bgPrimary) !important;
  border-top: 1px solid var(--mcp-borderPrimary) !important;
  padding: 16px 24px !important;
}

/* 表单元素在对话框中的样式 */
.el-dialog .el-form-item__label {
  color: var(--mcp-textPrimary) !important;
}

.el-dialog .el-input__wrapper {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

.el-dialog .el-input__inner {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
}

.el-dialog .el-input__inner::placeholder {
  color: var(--mcp-textSecondary) !important;
}

.el-dialog .el-textarea__wrapper {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

.el-dialog .el-textarea__inner {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
}

.el-dialog .el-textarea__inner::placeholder {
  color: var(--mcp-textSecondary) !important;
}

.el-table {
  background-color: transparent !important;
  color: var(--mcp-textPrimary) !important;
}

.el-table th.el-table__cell {
  background-color: var(--mcp-bgSecondary) !important;
}

.el-table tr {
  background-color: transparent !important;
}

.el-tag--success {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-success) !important;
  color: var(--mcp-success) !important;
}

.el-tag--danger {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-danger) !important;
  color: var(--mcp-danger) !important;
}

/* 针对指定类名的对话框的专门样式 */
.mcp-theme-dialog .el-dialog__body {
  background-color: var(--mcp-bgPrimary) !important;
  color: var(--mcp-textPrimary) !important;
  padding: 0 !important; /* 移除内边距，让内部组件控制自己的内边距 */
}

/* 确保对话框中的服务注册和配置管理组件背景色正确 */
.mcp-theme-dialog .service-register,
.mcp-theme-dialog .config-manager {
  background-color: var(--mcp-bgPrimary) !important;
  color: var(--mcp-textPrimary) !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  margin: 0 !important;
  padding: 24px !important;
}

/* 对话框中按钮的强制样式 */
.mcp-theme-dialog .el-button--primary {
  background-color: var(--mcp-primary) !important;
  border-color: var(--mcp-primary) !important;
  color: white !important;
}

.mcp-theme-dialog .el-button--primary:hover,
.mcp-theme-dialog .el-button--primary:focus {
  background-color: var(--mcp-primaryHover) !important;
  border-color: var(--mcp-primaryHover) !important;
}

.mcp-theme-dialog .el-button--default {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
  color: var(--mcp-textPrimary) !important;
}

/* 确保文本编辑器区域的样式正确 */
.mcp-theme-dialog .json-editor .el-textarea__inner {
  background-color: var(--mcp-bgSecondary) !important;
  color: var(--mcp-textPrimary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

/* 确保对话框内的标签元素使用正确的主题色 */
.mcp-theme-dialog .el-tag {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

.mcp-theme-dialog .el-tag--success {
  border-color: var(--mcp-success) !important;
  color: var(--mcp-success) !important;
}

.mcp-theme-dialog .el-tag--danger {
  border-color: var(--mcp-danger) !important;
  color: var(--mcp-danger) !important;
}

/* 文本按钮样式修复 */
.el-button--primary.is-text {
  color: var(--mcp-primary) !important;
  background-color: transparent !important;
}

.el-button--primary.is-text:hover,
.el-button--primary.is-text:focus {
  color: var(--mcp-primaryHover) !important;
  background-color: rgba(var(--mcp-primary-rgb, 211, 47, 47), 0.1) !important;
}

.el-button--default.is-text {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
}

.el-button--default.is-text:hover,
.el-button--default.is-text:focus {
  color: var(--mcp-primary) !important;
  background-color: rgba(var(--mcp-primary-rgb, 211, 47, 47), 0.1) !important;
}

/* 修复 Add Server 按钮文字对比度 */
.el-button {
  font-weight: 500 !important;
}
</style> 
