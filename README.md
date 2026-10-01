# StallSpan 市集摊档开间

沿街段一维 First-Fit 开间分配，挡柱不可被摊位跨越，输出分配图与放不下清单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4700 |
| API | http://localhost:9700 |
| API 文档 | http://localhost:9700/docs |
| Postgres | localhost:5448 |

健康检查：`GET http://localhost:9700/api/health`

## 使用说明

1. 在「集日」「街段」确认开市日与可用宽度。
2. 在「摊主」「挡柱」维护需求宽度与障碍位置；挡柱可在厚度之外登记外扩米数（禁入带 = 厚度半宽 + 外扩，填 0 只按厚度，负数直接打回）。
3. 打开「分配图」执行一维开间分配；邻柱外扩相交会合并成连续禁入带，改外扩后重新分配即按新值画空隙。
4. 在「放不下」查看无法安置的摊位（拒因只写空档不足 / 跨柱类）。

## 开发与测试

```bash
docker compose exec api pytest -q
```
