function initResultGraph(id, played, won, lost) {
	var other = played - won - lost;
	var s1 = [
	          ['Vunnet ('+won+')', won], 
	          ['Annet ('+other+')', other],
	          ['Tapt ('+lost+')', lost],
	          ];

	$.jqplot(id, [s1], {
		title:'Resultater',
		seriesColors: ['#90EE90', '#F0F03F', '#FC7E7E'],
		seriesDefaults:{
			renderer:$.jqplot.PieRenderer,
			rendererOptions: {
				showDataLabels: true
			}
		},
		legend: {
			show: true,
			rendererOptions: {
				numberRows: 1
			},
			location: 's'
		}
	});


}

function initRatingGraph(id, plotdata, labels) {
	// Create the dynamic label that behaves different when labels are supplied
	var customLegend = {};
	if (labels) {
		customLegend = {
				renderer: $.jqplot.EnhancedLegendRenderer,
				show: true,
				labels: labels,
				placement: 'outsideGrid',
				location: 'e',
				rendererOptions: {
					seriesToggle: "fast",
				},
		};
	}
		
	$.jqplot(id, plotdata, {
		title:'Rating utvikling',
		legend: customLegend,
		axes:{
			xaxis:{
				renderer:$.jqplot.DateAxisRenderer,
				tickOptions:{
					formatString:'%b&nbsp;%#d'
				}
			},
			yaxis:{
				tickOptions:{
					formatString:'%.0f'
				}
			}
		},
		highlighter: {
			show: true,
			sizeAdjust: 7.5
		},
		cursor: {
			show: true,
			zoom:true,
		}
	});
}

