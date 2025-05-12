# MCP Vue前端

基于Vue3开发的MCP服务前端项目，用于与MCP服务进行交互。该项目实现了与原Python版web_demo.py相同的功能，包括聊天交互、服务状态管理和配置管理。

## 功能特性

- 聊天界面：与MCP服务进行对话交互
- 服务状态：查看MCP服务的健康状态和连接的服务列表
- 服务注册：支持注册mcp.json中定义的服务、Docker环境本地服务和自定义服务
- 配置管理：查看和修改mcp.json配置文件

## 技术栈

- Vue 3：核心框架
- TypeScript：类型系统
- Vite：构建工具
- Element Plus：UI组件库
- Pinia：状态管理
- Axios：HTTP请求

## 开发环境设置

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

### 构建生产版本

```bash
npm run build
```

### 本地预览生产构建

```bash
npm run preview
```

## API代理配置

默认情况下，前端通过Vite的代理功能将API请求转发到后端FastAPI服务（端口18200）。
如需修改API地址，请编辑`vite.config.ts`文件中的代理配置。

## 部署说明

1. 构建项目：`npm run build`
2. 将`dist`目录下的文件部署到静态文件服务器
3. 确保MCP服务端已启动，前端可以正确访问到API端点

## 注意事项

- 本项目需要与MCP服务配合使用
- 确保服务端（FastAPI服务，端口18200）已正确启动
- 对于Docker环境，需要先启动相关容器服务 
