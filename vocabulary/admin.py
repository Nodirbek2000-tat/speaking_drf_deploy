import json
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.utils.html import format_html
from .models import Word, UserWord


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display  = ['word', 'level_badge', 'definition_short', 'has_translation', 'created_at']
    list_filter   = ['level']
    search_fields = ['word', 'definition']
    ordering      = ['level', 'word']
    change_list_template = 'admin/vocabulary/word_change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-json/',
                 self.admin_site.admin_view(self.import_json_view),
                 name='vocabulary_word_import_json'),
        ]
        return custom + urls

    def import_json_view(self, request):
        example = json.dumps([
            {
                "word": "eloquent",
                "level": "C1",
                "definition": "fluent or persuasive in speaking or writing",
                "translation_uz": "notiq, ifodali, ravon",
                "examples": [
                    "She gave an eloquent speech at the conference.",
                    "He was eloquent in his defense of the proposal."
                ]
            },
            {
                "word": "ambiguous",
                "level": "B2",
                "definition": "open to more than one interpretation; not clear",
                "translation_uz": "noaniq, ikki ma'noli",
                "examples": [
                    "The instructions were ambiguous and confusing.",
                    "His ambiguous answer left everyone puzzled."
                ]
            }
        ], ensure_ascii=False, indent=2)

        fields_doc = [
            ('word',           'Majburiy',  'Inglizcha so\'z (unique bo\'lishi kerak)'),
            ('level',          'Majburiy',  'A1 / A2 / B1 / B2 / C1 / C2'),
            ('definition',     'Majburiy',  'Inglizcha ta\'rif'),
            ('translation_uz', 'Ixtiyoriy', 'O\'zbekcha tarjima'),
            ('examples',       'Ixtiyoriy', 'Misol jumlalar massivi: ["...", "..."]'),
        ]

        context = {
            'title': 'Lug\'at So\'zlari — JSON Import',
            'opts':  self.model._meta,
            'example': example,
            'import_type': 'vocab',
            'back_url_resolved': reverse('admin:vocabulary_word_changelist'),
            'color': '#8b5cf6',
            'fields_doc': fields_doc,
        }

        if request.method == 'POST':
            raw = request.POST.get('json_data', '').strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                messages.error(request, f'JSON xato: {e}')
                return render(request, 'admin/ielts_mock/import_json_page.html', context)

            added = updated = skipped = 0
            VALID_LEVELS = {'A1', 'A2', 'B1', 'B2', 'C1', 'C2'}

            for item in data:
                if not isinstance(item, dict):
                    continue
                word_text = item.get('word', '').strip().lower()
                level     = item.get('level', '').strip().upper()
                defn      = item.get('definition', '').strip()
                tr        = item.get('translation_uz', '').strip()
                exs       = item.get('examples', [])

                if not word_text or not level or level not in VALID_LEVELS or not defn:
                    skipped += 1
                    continue

                obj, created = Word.objects.get_or_create(
                    word=word_text,
                    defaults={'level': level, 'definition': defn,
                              'translation_uz': tr, 'examples': exs}
                )
                if created:
                    added += 1
                else:
                    # Update if definition empty
                    if not obj.definition:
                        obj.definition = defn
                        obj.translation_uz = tr or obj.translation_uz
                        obj.examples = exs or obj.examples
                        obj.save()
                        updated += 1
                    else:
                        skipped += 1

            messages.success(
                request,
                f'✅ {added} ta yangi so\'z qo\'shildi, {updated} ta yangilandi, {skipped} ta o\'tkazib yuborildi.'
            )
            return redirect('admin:vocabulary_word_changelist')

        return render(request, 'admin/ielts_mock/import_json_page.html', context)

    def level_badge(self, obj):
        colors = {'A1':'#10b981','A2':'#34d399','B1':'#6366f1','B2':'#818cf8','C1':'#f59e0b','C2':'#ef4444'}
        c = colors.get(obj.level, '#6b7280')
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold">{}</span>', c, obj.level)
    level_badge.short_description = 'Daraja'

    def definition_short(self, obj):
        return obj.definition[:60] + ('…' if len(obj.definition) > 60 else '')
    definition_short.short_description = 'Ta\'rif'

    def has_translation(self, obj):
        if obj.translation_uz:
            return format_html('<span style="color:#10b981">✅</span>')
        return format_html('<span style="color:#ef4444">❌</span>')
    has_translation.short_description = 'Tarjima'


@admin.register(UserWord)
class UserWordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'word', 'saved_at']
    list_filter   = ['word__level']
    search_fields = ['user__username', 'word__word']
    raw_id_fields = ['user', 'word']
