# -*- coding: utf-8 -*-

from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.utils import simplejson
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.template import RequestContext
from django.db.models import Max, Min, Avg, Count
from models import *
from rating import RatingCalculator, RatingResult
from django.core.cache import cache
import calendar, copy
import logging
from datetime import timedelta
logger = logging.getLogger("file_logger")
#from django.db import transaction
#transaction.rollback()

def index(request):
    return render_to_response('index.html', {}, context_instance=RequestContext(request))

def players(request):
    places_strings = request.GET.getlist('places[]', None)

    # Validate that all places exists
    place_ids = []
    for place in places_strings:
        place_ids.append(get_object_or_404(Place, name=place).id)
    if not place_ids:
        place_ids = Place.objects.values_list('id', flat=True)
    place_ids = sorted(place_ids)
    
    # Create stats
    _update_ratings()
    match_winners_cache = {}
    players = []
    for player in Player.objects.all():
        player_results = PlayerResult.objects.filter(player=player)
        player_result_ids = player_results.values_list('match_id', flat=True)
        matches = Match.objects.filter(id__in=player_result_ids, place_id__in=place_ids)
        # Played - Win Ratio
        won = 0
        for match in matches:
            winners = match_winners_cache.get(match.id, False)
            if not winners: # Not in cache
                winners = match.get_winners()
                match_winners_cache[match.id] = winners
            if player in winners:
                won+=1
        played_count = matches.count()
        if played_count == 0:
            win_percent = 0
        else:
            win_percent = int(round(won*100.00/played_count))
        # Get last rating
        if player_results.exists():
            rating = int(player_results.order_by('-match__date', '-match__id')[0].rating)
        else:
            rating = "-"
        players.append({'id': player.id, 'name': player.name,
                        'played': played_count, 'won': won,
                        'win_perc': win_percent, 'rating': rating})
        
    places = []
    for place in Place.objects.all():
        p = {'name': place.name}
        p['selected'] = "selected" if (place.id in place_ids) else ""
        places.append(p)
    data = {'players': players, 'places': places, 
            'config': {'active_treshold': cur_config().active_player_match_treshold}}
    return render_to_response('players.html', data, context_instance=RequestContext(request))

def player(request, pid):
    _update_ratings()
    player = Player.objects.get(id=pid)
    player_result_ids = PlayerResult.objects.filter(player=player).values_list('match_id', flat=True)
    matches = Match.objects.filter(id__in=player_result_ids)
    # Won - Loss - Other counts
    won = 0
    lost = 0
    for match in matches:
        position = match.get_position(player.id)
        if position == 1:
            won += 1
        elif position == PlayerResult.objects.filter(match=match).count():
            lost += 1
    data = {'name': player.name, 'id': player.id, 'won': won, 'lost': lost, 
            'played': matches.count(), 'ratings': player.get_ratings()}
    return render_to_response('player.html', data, context_instance=RequestContext(request))

def matches(request):
    places = {}
    for place in Place.objects.all():
        places[place.id] = place.name
    matches = []
    for match in Match.objects.all().order_by("-date", "-id"):
        matches.append({'id': match.id,
                        'year': match.date.year, 
                        'month': _month_name(match.date.month),
                        'place': places[match.place_id]})
    data = {'matches': matches}
    return render_to_response('matches.html', data, context_instance=RequestContext(request))

def match(request, mid):
    _update_ratings()
    # Get match
    m = Match.objects.select_related('place').get(id=mid)
    results = []
    # Get players result for match
    for result in PlayerResult.objects.select_related('player', 'match__date').filter(match=m):
        vals = result.vals()
        if vals['player']['id'] in [p.id for p in m.get_winners()]:
            vals['winner'] = True
        else:
            vals['winner'] = False
        results.append(vals)
    # Sort matches by game position
    results = sorted(results, key=lambda result: result['total'])
    # Create context data and return http request
    data = {'year': m.date.year,
            'month': _month_name(m.date.month),
            'day': m.date.day,
            'place': m.place.name,
            'results': results,
            'next_match_id': m.get_next_match_id(),
            'prev_match_id': m.get_prev_match_id(),
            'moffa_los': results[len(results)-1]['player']['name'] == "Bengt",
            'moffa_win': (results[0]['player']['name'] == "Bengt") and (results[0]['total'] < 0),
            'aase_los': results[len(results)-1]['player']['name'] == "Aase",
            'andre_win': results[0]['player']['name'] == u"André"}
    return render_to_response('match.html', data, context_instance=RequestContext(request))


def stats(request):
    """ This is the stats page that show all the stats that didnt fit
    anywhere else.
    
    """
    ALL_RESULTS = PlayerResult.objects.select_related() # User several times
    PRS = PlayerResultStatser(ALL_RESULTS)
        
    results_totals = ALL_RESULTS.extra(select={'total': '(sum_spades + sum_queens + sum_solitaire_lines + sum_solitaire_cards + sum_pass - sum_grand - sum_trumph)'})
    total_avg = sum([r.total for r in results_totals])/results_totals.count()
    best_match_result = PRS.bot_total(1)[0]
    worst_match_result = PRS.top_total(1)[0]

    data = {'spades': {'worst': PRS.minmax(Max, 'spades'),
                       'average': PRS.gt0_avg("spades")},
            
            'queens': {'worst': PRS.minmax(Max, 'queens'),
                       'average': PRS.gt0_avg("queens")},
            
            'solitaire_lines': {'worst': PRS.minmax(Max, "solitaire_lines"),
                                'average': PRS.gt0_avg("solitaire_lines")},
            'solitaire_cards': {'worst': PRS.minmax(Max, "solitaire_cards"),
                                'average': PRS.gt0_avg("solitaire_cards")},
            'solitaire_total': {'worst': PRS.top(1, "sum_solitaire_lines + sum_solitaire_cards")[0]},
            
            'pass': {'worst': PRS.minmax(Max, 'pass')},
            
            'grand': {'best': PRS.minmax(Max, 'grand')},
            
            'trumph': {'best': PRS.minmax(Max, 'trumph')},
            
            'extremes': {'gain': PRS.top(1, "sum_spades + sum_queens + sum_solitaire_lines + sum_solitaire_cards + sum_pass")[0],
                         'loss': PRS.bot(1, "0 - sum_grand - sum_trumph")[0],
                         'match_size': Match.objects.annotate(count=Count("playerresult")).order_by("-count", "date", "id").values("id", "count")[0]},
            
            'total': {'best': best_match_result,
                    'worst': worst_match_result,
                    'average': total_avg},
            }   
    return render_to_response('stats.html', data, context_instance=RequestContext(request))

def stats_best_results(request):
    amount = int(request.GET.get("amount", 20))
    PRS = PlayerResultStatser(PlayerResult.objects.select_related())
    data = {'results': PRS.bot_total(amount)}
    return render_to_response('stats-top-results.html', data, context_instance=RequestContext(request))
   
def stats_worst_results(request):
    amount = int(request.GET.get("amount", 20))
    PRS = PlayerResultStatser(PlayerResult.objects.select_related())
    data = {'results': PRS.top_total(amount)}
    return render_to_response('stats-top-results.html', data, context_instance=RequestContext(request))

def rating(request):
    _update_ratings()
    if PlayerResult.objects.count() == 0:
        return render_to_response('rating.html', {}, context_instance=RequestContext(request))
    max_rating = PlayerResult.objects.aggregate(Max('rating'))['rating__max']
    max_obj = PlayerResult.objects.select_related('player__name').filter(rating = max_rating).order_by('match__date', 'match__id')[0]
    min_rating = PlayerResult.objects.aggregate(Min('rating'))['rating__min']
    min_obj = PlayerResult.objects.select_related('player__name').filter(rating = min_rating).order_by('match__date', 'match__id')[0]
    players = Player.objects.all()
    data = {'max': {'pid': max_obj.player_id, 'pname': max_obj.player.name, 
                    'mid': max_obj.match_id, 'rating': max_obj.rating},
            'min': {'pid': min_obj.player_id, 'pname': min_obj.player.name, 
                    'mid': min_obj.match_id, 'rating': min_obj.rating},
            'players': [p.get_ratings() for p in players],
            'player_names': [p.name for p in players],
            }
    return render_to_response('rating.html', data, context_instance=RequestContext(request))

def rating_description(request):
    conf = cur_config()
    data = {'K_VALUE': int(conf.rating_k), 
            'START_RATING': int(conf.rating_start)}
    return render_to_response('rating-description.html', data, context_instance=RequestContext(request))

def activity(request):
    matches = Match.objects.select_related('place').order_by('date')
    
    # First do a temporarly dynamic count that spawns from the start to the end
    data = {}
    first_year = matches[0].date.year
    last_year = matches[len(matches)-1].date.year
    for match in matches:
        place = match.place.name
        if not data.has_key(place):
            data[place] = {}
            for year in range(first_year, last_year+1):
                data[place][year] = {}
                for month in range(1,13):
                    data[place][year][month] = 0
        # Add data
        data[place][match.date.year][match.date.month] += 1
        
    # use temporarly data to create fitting array for the template grapher
    activity = {'places': [], 'activity': []}
    for place in data:
        place_activity = []
        for year in data[place]:
            for month in data[place][year]:
                c = data[place][year][month]
                if month < 10:
                    month = "0%s" % month
                place_activity.append(["%s-%s-15" % (year,month), c])
        activity['places'].append(str(place))
        activity['activity'].append(place_activity)
    return render_to_response('activity.html', activity, context_instance=RequestContext(request))

def _month_name(month_number):
    return calendar.month_name[month_number]

calc = RatingCalculator()
def _update_ratings():
    START_RATING = cur_config().rating_start
    players = {}
    match_ids = list(set(PlayerResult.objects.filter(rating=None).values_list('match_id', flat=True)))
    for match in Match.objects.filter(id__in=match_ids).order_by('date', 'id'):
        player_positions = match.get_positions()
        rating_results = []
        for p in player_positions:
            # Fetch the current rating value
            #if not players.get(p['id'], False):
                rated_results = PlayerResult.objects.filter(player=p['id']).exclude(rating=None).order_by('-match__date', '-match__id')
                if not rated_results.exists():
                    rating = START_RATING
                else:
                    rating = rated_results[0].rating
            #else:
            #    rating = players[p['id']]
                rating_results.append(RatingResult(p['id'], rating, p['position']))
        # Calculate new ratings
        new_player_ratings = calc.new_ratings(rating_results)
        # Update
        for p in new_player_ratings:
            players[p.dbid] = p.rating
            PlayerResult.objects.filter(player=p.dbid).filter(match=match).update(rating=p.rating)
            
class PlayerResultStatser:
    """ Does all kind of statistical fun fact calculations with the
    supplied PlayerResult object.
    
    """
    ALL_RESULTS = None
    
    def __init__(self, all_results):
        self.ALL_RESULTS = all_results
    
    def minmax(self, aggfunc, round_type):
        """ Returns min or max value for a round type"""
        field = "sum_"+round_type
        val = self.ALL_RESULTS.aggregate(aggfunc(field))[field+'__max']
        results = self.ALL_RESULTS.filter(**{field: val})
        first = results.order_by('match__date', 'match__id').select_related()[0]
        return {'sum': val, 'mid': first.match_id,
                'pid': first.player_id, 'pname': first.player.name}
        
    def gt0_avg(self, round_type):
        field = "sum_"+round_type
        result = self.ALL_RESULTS.filter(**{field+"__gt": 0}).aggregate(Avg(field))
        return round(result[field+'__avg'],1)
    
    def top_total(self, amount):
        return self.top(amount, "sum_spades + sum_queens + sum_solitaire_lines + sum_solitaire_cards + sum_pass - sum_grand - sum_trumph")
    def bot_total(self, amount):
        return self.bot(amount, "sum_spades + sum_queens + sum_solitaire_lines + sum_solitaire_cards + sum_pass - sum_grand - sum_trumph")
    
    def bot(self, amount, value_field):
        return self.top(amount, value_field, "")
    
    def top(self, amount, value_field_usage, total_prechar="-"):
        select_query = {'total': '('+value_field_usage+')'}
        results = self.ALL_RESULTS.extra(select=select_query).order_by(total_prechar+'total', 'match__date', 'match__id')
        top = []
        for i in range(min(results.count(), amount)):
            top.append({'sum': results[i].total, 'mid': results[i].match_id,
                        'pid': results[i].player_id, 'pname': results[i].player.name})
        return top