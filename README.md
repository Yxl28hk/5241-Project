# 知行学习平台

这是一个使用 **Python Flask + Neon PostgreSQL + HTML/CSS/JavaScript** 构建的学习平台示例。

## 启动项目

在项目目录打开 PowerShell：

```powershell
python -m pip install -r requirements.txt

# 首次使用时编辑 .env，把 Neon 控制台 Connect 页面中的连接字符串填入 DATABASE_URL
python app.py
```

然后访问 <http://127.0.0.1:5000>。

首次启动会自动在 Neon 数据库中创建：

- `users`、`courses`、`learning_records`：应用数据表
- `uploads/`：课程文件保存目录

应用会自动读取项目根目录的 `.env`，不需要每次启动时重复设置环境变量。
`DATABASE_URL` 是必需配置，建议使用 Neon 的 pooled connection string，并保留
`sslmode=require`。`.env` 已加入 Git 忽略规则，不要把真实连接字符串提交到 Git。
可以参考 [.env.example](C:/Users/31033/OneDrive/Desktop/学习/5241-Project/.env.example)
填写本地 `.env`。

## 已提供的后端接口

- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `POST /api/auth/logout`：退出登录
- `GET /api/auth/me`：获取当前登录用户
- `PATCH /api/profile`：修改昵称和头像
- `PATCH /api/profile/password`：修改密码
- `DELETE /api/profile`：注销当前账号，同时删除其学习记录、上传课程及课程文件
- `GET /api/courses?q=&category=`：搜索和筛选课程
- `POST /api/courses`：登录后上传课程和资源文件
- `GET /api/profile/courses`：普通用户查看自己上传的课程，管理员查看平台全部课程
- `GET /api/profile/learning`：查看当前用户正在学习的课程
- `POST /api/courses/<id>/learn`：将课程加入学习记录
- `DELETE /api/profile/learning/<id>`：停止学习当前用户列表中的课程
- `GET /api/courses/<id>/learners`：教师查看自己课程、管理员查看任意课程的学习人员（仅返回昵称、进度和更新时间）
- `DELETE /api/courses/<id>/learners/<user_id>`：教师或管理员移除课程学习记录，不会删除用户账号
- `DELETE /api/courses/<id>`：删除当前用户自己上传的课程及其文件
- `GET /api/admin/users`：管理员查看所有账户、教师创建的课程和学生学习记录

## 账号角色

- 学生：只能浏览和学习课程，不能上传或管理课程资源
- 教师：可以上传、查看和管理自己上传的课程
- 管理员：拥有平台全部资源管理权限，也可以上传课程

## 管理员账号

首次启动会自动创建管理员账号。默认开发环境账号为：

```text
邮箱：admin@zhixing.com
密码：Admin@123456
```

生产环境请在启动前设置自己的管理员配置：

```powershell
$env:ZHIXING_ADMIN_EMAIL="your-admin@example.com"
$env:ZHIXING_ADMIN_PASSWORD="your-strong-password"
```

管理员登录后可以在“资源管理”中查看平台全部课程并删除任意课程；普通用户只能查看和删除自己上传的课程。删除课程时，也会删除该课程的学习记录和上传文件。
- `GET /uploads/<filename>`：访问已上传资源

## 上传限制

支持 PDF、Word、PPT、MP4 和 MOV，单个文件最大 500MB。生产环境部署时请设置随机的 `ZHIXING_SECRET_KEY` 环境变量，并使用 HTTPS。
