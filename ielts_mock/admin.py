import json
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.utils.html import format_html
from .models import IELTSQuestion, IELTSPart1Question, IELTSPart23Set, IELTSSession, IELTSAnswer

# ─── Part 3 Inline (Part 2 sahifasida) ────────────────────────────────────────

class Part3Inline(admin.TabularInline):
    model = IELTSQuestion
    fk_name = 'related_part2'
    extra = 2
    fields = ['question', 'is_active']
    verbose_name = "Part 3 savol"
    verbose_name_plural = "Part 3 savollar (shu Part 2 ga bog'liq)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(part=3)

    def save_new_instance(self, parent, instance):
        instance.part = 3
        return instance


# ─── IELTS Part 1 Admin ────────────────────────────────────────────────────────

@admin.register(IELTSPart1Question)
class IELTSPart1Admin(admin.ModelAdmin):
    list_display  = ['q_short', 'is_active', 'created_at']
    list_filter   = ['is_active']
    list_editable = ['is_active']
    search_fields = ['question']
    ordering      = ['id']
    change_list_template = 'admin/ielts_mock/part1_change_list.html'

    fields = ('question', 'is_active')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(part=1)

    def save_model(self, request, obj, form, change):
        obj.part = 1
        super().save_model(request, obj, form, change)

    def q_short(self, obj):
        return obj.question[:80] + ('…' if len(obj.question) > 80 else '')
    q_short.short_description = 'Savol'

    # ── JSON Import ──────────────────────────────────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-json/',
                 self.admin_site.admin_view(self.import_json_view),
                 name='ielts_part1_import_json'),
        ]
        return custom + urls

    def import_json_view(self, request):
        example = json.dumps([
            {"question": "Do you work or study?", "is_intro": False},
            {"question": "What do you do in your free time?", "is_intro": False},
            {"question": "Can you tell me your full name, please?", "is_intro": True}
        ], ensure_ascii=False, indent=2)

        context = {
            'title': 'Part 1 Savollar — JSON Import',
            'opts':  self.model._meta,
            'example': example,
            'import_type': 'part1',
            'back_url_resolved': reverse('admin:ielts_mock_ieltspart1question_changelist'),
            'color':   '#6366f1',
            'fields_doc': [
                ('question',  'Majburiy',  'Savol matni (string)'),
                ('is_intro',  'Ixtiyoriy', 'true yoki false — kirish savoli (default: false)'),
            ],
        }

        if request.method == 'POST':
            raw = request.POST.get('json_data', '').strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                messages.error(request, f'JSON xato: {e}')
                return render(request, 'admin/ielts_mock/import_json_page.html', context)

            count = 0
            for item in data:
                if isinstance(item, str):
                    q_text = item.strip()
                    is_intro = False
                elif isinstance(item, dict):
                    q_text   = item.get('question', '').strip()
                    is_intro = bool(item.get('is_intro', False))
                else:
                    continue
                if q_text:
                    IELTSQuestion.objects.create(part=1, question=q_text, is_intro=is_intro)
                    count += 1

            messages.success(request, f'✅ {count} ta Part 1 savol qo\'shildi!')
            return redirect('admin:ielts_mock_ieltspart1question_changelist')

        return render(request, 'admin/ielts_mock/import_json_page.html', context)


# ─── IELTS Part 2+3 Admin ─────────────────────────────────────────────────────

@admin.register(IELTSPart23Set)
class IELTSPart23Admin(admin.ModelAdmin):
    list_display  = ['q_short', 'part3_count', 'is_active', 'created_at']
    list_filter   = ['is_active']
    list_editable = ['is_active']
    search_fields = ['question']
    ordering      = ['id']
    change_list_template = 'admin/ielts_mock/part23_change_list.html'

    fieldsets = (
        ('Asosiy', {
            'fields': ('question', 'is_active'),
            'description': 'Part 2 — Cue Card mavzu sarlavhasi yoki asosiy savol.'
        }),
        ('Cue Card nuqtalari', {
            'fields': ('cue_card_points',),
            'description': 'JSON massiv: ["where you went", "who you went with", ...]'
        }),
    )
    inlines = [Part3Inline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(part=2)

    def save_model(self, request, obj, form, change):
        obj.part = 2
        super().save_model(request, obj, form, change)

    def q_short(self, obj):
        return obj.question[:70] + ('…' if len(obj.question) > 70 else '')
    q_short.short_description = 'Cue Card mavzu'

    def part3_count(self, obj):
        cnt = obj.part3_follow_up.filter(is_active=True).count()
        color = '#10b981' if cnt >= 2 else '#f59e0b'
        return format_html(
            '<span style="color:{};font-weight:bold">{} ta Part 3</span>',
            color, cnt
        )
    part3_count.short_description = 'Part 3 savollar'

    # ── JSON Import ──────────────────────────────────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-json/',
                 self.admin_site.admin_view(self.import_json_view),
                 name='ielts_part23_import_json'),
        ]
        return custom + urls

    def import_json_view(self, request):
        example = json.dumps([
            {
                "topic": "A memorable journey",
                "cue_points": ["where you went", "who you went with", "what you did there", "and explain why it was memorable"],
                "part3_questions": [
                    "How has tourism changed in your country in recent years?",
                    "What are the advantages of travelling to different countries?",
                    "Do you think it is better to travel alone or with a group? Why?"
                ]
            }
        ], ensure_ascii=False, indent=2)

        context = {
            'title': 'Part 2+3 (Cue Cards) — JSON Import',
            'opts':  self.model._meta,
            'example': example,
            'import_type': 'part23',
            'back_url_resolved': reverse('admin:ielts_mock_ieltspart23set_changelist'),
            'color':   '#10b981',
            'fields_doc': [
                ('topic',           'Majburiy',  'Cue card mavzu nomi / asosiy savol matni'),
                ('cue_points',      'Ixtiyoriy', 'Nuqtalar massivi: ["where you went", ...]'),
                ('part3_questions', 'Ixtiyoriy', 'Part 3 savollar massivi: ["How has ...", ...]'),
            ],
        }

        if request.method == 'POST':
            raw = request.POST.get('json_data', '').strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                messages.error(request, f'JSON xato: {e}')
                return render(request, 'admin/ielts_mock/import_json_page.html', context)

            count_p2 = count_p3 = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                topic     = item.get('topic', '').strip()
                cue_pts   = item.get('cue_points', [])
                p3_qs     = item.get('part3_questions', [])
                if not topic:
                    continue

                p2 = IELTSQuestion.objects.create(
                    part=2,
                    question=topic,
                    cue_card_points=cue_pts or None,
                )
                count_p2 += 1

                for q3 in p3_qs:
                    if isinstance(q3, str) and q3.strip():
                        IELTSQuestion.objects.create(
                            part=3,
                            question=q3.strip(),
                            related_part2=p2,
                        )
                        count_p3 += 1

            messages.success(
                request,
                f'✅ {count_p2} ta Cue Card (Part 2) va {count_p3} ta Part 3 savol qo\'shildi!'
            )
            return redirect('admin:ielts_mock_ieltspart23set_changelist')

        return render(request, 'admin/ielts_mock/import_json_page.html', context)


# ─── IELTSSession Admin ────────────────────────────────────────────────────────

class IELTSAnswerInline(admin.TabularInline):
    model      = IELTSAnswer
    extra      = 0
    readonly_fields = ['question', 'transcript', 'created_at']
    can_delete = False
    max_num    = 0


@admin.register(IELTSSession)
class IELTSSessionAdmin(admin.ModelAdmin):
    list_display    = ['user', 'overall_band_display', 'is_completed', 'started_at']
    list_filter     = ['is_completed']
    search_fields   = ['user__username', 'user__first_name']
    readonly_fields = [
        'user', 'started_at', 'ended_at', 'overall_band',
        'sub_scores', 'strengths', 'improvements',
        'mistakes', 'recommendations', 'is_completed'
    ]
    inlines = [IELTSAnswerInline]

    def overall_band_display(self, obj):
        if obj.overall_band:
            color = '#10b981' if obj.overall_band >= 7 else '#f59e0b' if obj.overall_band >= 5.5 else '#ef4444'
            return format_html(
                '<span style="color:{};font-weight:bold;font-size:16px">Band {}</span>',
                color, obj.overall_band
            )
        return '—'
    overall_band_display.short_description = 'Band'
