# iconfont 管理工具

由于 iconfont.cn 上传图标需要审核，审核时间不定，导致效率低下，所以开发了这个工具来管理项目图标，方便项目使用。

- 支持多项目，多项目之间互不影响。
- svg 生成 iconfont.ttf 文件。
- 支持生成 dart, css, swift 代码。
- 支持用户认证，限制公开访问。

## 安装

```shell
docker pull twosx/iconfont-tool:latest

docker run -d -p 8080:8080 -v ./data:/app/data --name iconfont-tool twosx/iconfont-tool:latest
```

### 环境变量

| 变量名                 | 说明     | 默认值   |
|---------------------|--------|-------|
| TOOL_ADMIN_USERNAME | 初始登录用户 | admin |
| TOOL_ADMIN_PASSWORD | 初始登录密码 | admin |