# -*- coding: utf-8 -*-

from mokstats.models import *
from django.contrib import admin
from django import forms
from django.contrib.auth.models import User, Group


class ResultInlineFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        # get forms that actually have valid data
        player_count = 0
        spades_total = 0
        queens_total = 0
        pass_total = 0
        grand_total = 0
        trumph_total = 0
        players_with_zero_solitaire_cards = 0
        for form in self.forms:
            try:
                if form.cleaned_data:
                    player_count += 1

                    spades_total += form.cleaned_data['sum_spades']

                    sum_queens = form.cleaned_data['sum_queens']
                    if not sum_queens % 4 == 0:
                        raise forms.ValidationError('Ulovlig dameverdi, %s er gitt, bare multiplikasjon av 4 er lovlig' % sum_queens)
                    queens_total += sum_queens

                    if form.cleaned_data['sum_solitaire_cards'] == 0:
                        players_with_zero_solitaire_cards += 1

                    pass_total += form.cleaned_data['sum_pass']
                    grand_total += form.cleaned_data['sum_grand']
                    trumph_total += form.cleaned_data['sum_trumph']
            except AttributeError:
                pass
        if player_count < 3:
            raise forms.ValidationError('Minst 3 spillere')

        if player_count in [6, 8, 9]:
            spades_in_play = 12
        else:
            spades_in_play = 13
        if not spades_total == spades_in_play:
            raise forms.ValidationError('For få/mange Spa poeng gitt, %s totalt nå, %s krevd' % (spades_total, spades_in_play))

        if not queens_total == 16:
            raise forms.ValidationError('For få/mange Damer poeng gitt, %s totalt nå, 16 krevd' % queens_total)

        if players_with_zero_solitaire_cards != 1:
            raise forms.ValidationError('For få/mange spillere med 0 kort igjen i Kabal, %s nå, 1 krevd' % players_with_zero_solitaire_cards)

        cards_per_player = 52 / player_count

        if not pass_total == cards_per_player:
            raise forms.ValidationError('For få/mange Pass poeng gitt, %s totalt nå, %s krevd' % (pass_total, cards_per_player))
        if not grand_total == cards_per_player:
            raise forms.ValidationError('For få/mange Grand poeng gitt, %s totalt nå, %s krevd' % (grand_total, cards_per_player))
        if not trumph_total == cards_per_player:
            raise forms.ValidationError('For få/mange Trumf poeng gitt, %s totalt nå, %s krevd' % (trumph_total, cards_per_player))


class ResultInline(admin.TabularInline):
    exclude = ('rating',)
    readonly_fields = ['total', ]
    model = PlayerResult
    formset = ResultInlineFormset
    extra = 0
    min_num = 3


class MatchAdmin(admin.ModelAdmin):
    inlines = [ResultInline, ]

    class Media:
        js = ("https://code.jquery.com/jquery-1.8.2.min.js",
              "admin_custom.js",)
        css = {'all': ('admin_custom.css',)}


class ConfigurationAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('admin_custom.css',)}


admin.site.register(Player)
admin.site.register(Place)
admin.site.register(Match, MatchAdmin)
admin.site.register(Configuration, ConfigurationAdmin)
