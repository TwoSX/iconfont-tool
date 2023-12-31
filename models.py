from tortoise import fields, models


# 项目表
class Project(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    icons = fields.ReverseRelation["Icon"]

    def __str__(self):
        return self.name


# 图标表
class Icon(models.Model):
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="icons")
    name = fields.CharField(max_length=255)
    content = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    # unicode 为 id + 0xe000
    def unicode(self) -> str:
        return hex(self.id + 0xE000)

    def __str__(self):
        return self.name


# 用户表
class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255)
    password = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return self.username
