import json
from django.contrib import admin
from django.conf import settings
from .models import Word, UserWord


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ["word", "level", "definition_preview", "has_translation", "created_at"]
    list_filter = ["level"]
    search_fields = ["word"]
    fields = ["word", "level", "definition", "translation_uz", "examples"]
    help_texts = {
        'word': "So'zni kiriting — ta'rif, tarjima va misollar AI tomonidan avtomatik to'ldiriladi"
    }

    def definition_preview(self, obj):
        return (obj.definition or "")[:70]
    definition_preview.short_description = "Ta'rif"

    def has_translation(self, obj):
        return bool(obj.translation_uz)
    has_translation.boolean = True
    has_translation.short_description = "O'zbekcha"

    def save_model(self, request, obj, form, change):
        if not obj.definition or not obj.translation_uz:
            try:
                data = self._ai_lookup(obj.word)
                if data:
                    if not obj.definition:
                        obj.definition = data.get('definition', '')
                    if not obj.translation_uz:
                        obj.translation_uz = data.get('translation_uz', '')
                    if not obj.examples:
                        obj.examples = data.get('examples', [])
                    if not obj.level or obj.level == 'B1':
                        obj.level = data.get('level', 'B1')
                    self.message_user(request, f"'{obj.word}' uchun AI ma'lumotlar to'ldirildi!")
            except Exception as e:
                self.message_user(request, f"AI xato: {e}", level='warning')
        super().save_model(request, obj, form, change)

    def _ai_lookup(self, word: str) -> dict:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an English vocabulary expert."},
                {"role": "user", "content": (
                    f'For the word "{word}", return JSON:\n'
                    '{\n'
                    '  "word": "exact word",\n'
                    '  "level": "B1",\n'
                    '  "definition": "Clear English definition in 1-2 sentences",\n'
                    '  "translation_uz": "O\'zbekcha tarjima",\n'
                    '  "examples": [\n'
                    '    "Example sentence 1 using the word in context.",\n'
                    '    "Example sentence 2 with the word naturally.",\n'
                    '    "Example sentence 3 from academic context."\n'
                    '  ]\n'
                    '}\n'
                    'Level must be one of: A1, A2, B1, B2, C1, C2'
                )}
            ],
            response_format={"type": "json_object"},
            max_tokens=400
        )
        return json.loads(resp.choices[0].message.content)


@admin.register(UserWord)
class UserWordAdmin(admin.ModelAdmin):
    list_display = ["user", "word", "saved_at"]
    search_fields = ["user__username", "word__word"]
