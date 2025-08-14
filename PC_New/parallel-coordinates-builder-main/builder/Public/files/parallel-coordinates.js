(function(d3) {

  window.parallel = function(model, colors) {
    var self = {},
        dimensions,
        dragging = {},
        highlighted = null,
        // TODO: nicer way to do this
        //  like, map of graphics objects that are toggled renderable based on filter
        // this maintains a hash of data item lines that should not be displayed
        undisplayable = {},
        container = document.getElementById("parallel").parentElement 

    var line = d3.line().curve(d3.curveCardinal.tension(0.85)),
        axis = d3.axisLeft(),
        foreground;
  
    var myData = model.get('data');

    self.opacity = 1.0;
    const app = new PIXI.Application({ 
      backgroundAlpha: 0,
      resizeTo: container, 
      width: parseInt(container.clientWidth), 
      height: parseInt(container.clientHeight),
      antialias: true,
      autoDensity: true,
      resolution: 2
    });

    document.getElementById("parallel").append(app.view);

    const resizeObserver = new ResizeObserver(() => {
      app.renderer.resize(container.clientWidth, container.clientHeight);
      self.render()
    });

    resizeObserver.observe(container);


    const pixiLines = new PIXI.Graphics();
    const highlightedLine = new PIXI.Graphics();

    self.update = function(data) {
      myData = data;
    };
    
    self.render = function() {
      
      // TODO: could refactor these renderPIXI functions
      // to be the one function rendering a container of graphics
      self.renderPIXI = function(graphics) {

        graphics.clear()

        var unHighlighted = myData.filter(function(z, d) {
          return z != highlighted
        })

        unHighlighted.forEach(d => {
          if (undisplayable[d["id"]]) {
            return;
          }
          prevX = x(x.domain()[0]) + m[1]
          prevY = y[x.domain()[0]](d[x.domain()[0]]) + m[0]
          // console.log(prevX, prevY)
          graphics.moveTo(prevX, prevY)

          graphics.lineStyle({
            width: 1, 
            color: colors[d["State"]], 
            // color: 0xFF0000, 
            // hook up to opacity slider
            alpha: highlighted ? 0.1: self.opacity,
            // alpha: 0.35,
            // native: true
          });

          // use path()
          const commands = path(d).toString().split(/(?=[MLC])/);
          commands.forEach(command => {
              const type = command[0];
              const args = command.slice(1).trim().split(/[\s,]+/).map(Number);
              if (type === 'M') {
                  graphics.moveTo(args[0] + m[3], args[1] + m[0]);
                  // points.push({ x: args[0], y: args[1] });
              } else if (type === 'L') {
                  graphics.lineTo(args[0]+ m[3], args[1] + m[0]);
                  // points.push({ x: args[0], y: args[1] });
              } else if (type === 'C') {
                  graphics.bezierCurveTo(
                    args[0]+ m[3], args[1] + m[0], 
                    args[2]+ m[3], args[3] + m[0], 
                    args[4]+ m[3], args[5] + m[0]);
                  // points.push({ x: args[0], y: args[1] })
                  // points.push({ x: args[2], y: args[3] })
                  // points.push({ x: args[4], y: args[5] })
              }
          });
        });

        return graphics;
      }

      self.renderHighlightedPIXI = function(graphics) {

        graphics.clear()

        // console.log("highlighted!", highlighted)
        if (highlighted) {
          prevX = x(x.domain()[0]) + m[1]
          prevY = y[x.domain()[0]](highlighted[x.domain()[0]]) + m[0]
          
          graphics.moveTo(prevX, prevY)
          .lineStyle({
            width: 2, 
            color: colors[highlighted["State"]], 
            alpha: 1,
            native: false
          });
  
          const commands = path(highlighted).toString().split(/(?=[MLC])/);
          commands.forEach(command => {
              const type = command[0];
              const args = command.slice(1).trim().split(/[\s,]+/).map(Number);
              if (type === 'M') {
                  graphics.moveTo(args[0] + m[3], args[1] + m[0]);
                  // points.push({ x: args[0], y: args[1] });
              } else if (type === 'L') {
                  graphics.lineTo(args[0]+ m[3], args[1] + m[0]);
                  // points.push({ x: args[0], y: args[1] });
              } else if (type === 'C') {
                  graphics.bezierCurveTo(
                    args[0]+ m[3], args[1] + m[0], 
                    args[2]+ m[3], args[3] + m[0], 
                    args[4]+ m[3], args[5] + m[0]);
                  // points.push({ x: args[0], y: args[1] })
                  // points.push({ x: args[2], y: args[3] })
                  // points.push({ x: args[4], y: args[5] })
              }
          });
          // console.log("highlighted line:", highlighted)
        }

        return graphics;
      }

      // container.select("svg").remove();
      d3.select("#parallel").select("svg").remove();
      
      var bounds = [ container.clientWidth, container.clientHeight ],
          m = [30, 10, 10, 10],
          nullOffset = 15,
          w = bounds[0] - m[1] - m[3],
          h = bounds[1] - m[0] - m[2] - nullOffset;

      app.renderer.resize(bounds[0], bounds[1])

      var x = d3.scalePoint().range([0, w]).padding(1),
          y = {},
          ySelections = {}

      // var svg = container.append("svg:svg")
      var svg = d3.select("#parallel").append("svg:svg")
          .style("position", "absolute")
          .style("left", 0)
          .style("top", 0)
          .style("z-index", 2)
          .attr("width", w + m[1] + m[3])
          .attr("height", h + m[0] + m[2] + nullOffset)
        .append("svg:g")
          .attr("transform", "translate(" + m[3] + "," + m[0] + ")");

      // Extract the list of dimensions and create a scale for each.
      x.domain(dimensions = Object.keys(myData[0]).filter(function(d) {

        var excludes = [];
        var ex = d != "id" && (excludes.indexOf(d) < 0);

        // ordinal categories
        if (["Institution", "State", "group"].indexOf(d) >= 0) {
          return ex &&
          (y[d] = d3.scalePoint()
            .domain(myData.map(function(p) { return p[d]; }).filter(z => z !== 'null'))
            .range([h, 0]));
        }

        return ex &&
          (y[d] = d3.scaleLinear()
          .domain(d3.extent(myData, function(p) { return +p[d]; }).filter(z => z !== 'null')).nice()
          .range([h, 0]).unknown(h + nullOffset));
        }));

      // console.log(x.domain())
      
      // Add lines for focus.
      foreground = svg.append("svg:g")
          .attr("class", "foreground")
        .selectAll("path")
          .data(myData)
        // .enter().append("svg:path")
          // .attr("d", path)
          // .attr("style", function(d) {
          //   return "stroke:" + colors[d.group] + ";";
          // });

      // Draw the line chart
      self.renderPIXI(pixiLines)
      self.renderHighlightedPIXI(highlightedLine)

      var mySrcElement;

      // Add a group element for each dimension.
      var g = svg.selectAll(".dimension")
          .data(dimensions)
        .enter().append("svg:g")
          .attr("class", "dimension")
          .attr("transform", function(d) { return "translate(" + x(d) + ")"; })
          .call(d3.drag()
            .on("start", function(event, d) {
              mySrcElement = event.sourceEvent.srcElement
              // console.log(event.sourceEvent)
              if (mySrcElement && (mySrcElement.nodeName !== "text")) {
                return
              }
              dragging[d] = this.__origin__ = x(d);
            })
            .on("drag", function(event, d) {
              if (!dragging[d]) return;

              dragging[d] = Math.min(w, Math.max(0, this.__origin__ += event.dx));
              // foreground.attr("d", path); // this should put numbers into a graphics points array (draw with quad curve)
              dimensions.sort(function(a, b) { return position(a) - position(b); });
              x.domain(dimensions);
              g.attr("transform", function(d) { return "translate(" + position(d) + ")"; })

              self.renderPIXI(pixiLines)
              self.renderPIXI(highlightedLine)

            })
            .on("end", function(event, d) {
              if (mySrcElement && (mySrcElement.nodeName !== "text")) {
                return
              }

              // console.log('drag end start', event)
              delete this.__origin__;
              delete dragging[d];
              transition(d3.select(this)).attr("transform", "translate(" + x(d) + ")")
              .tween("loggy", function() {
                return function(t) {
                  self.renderPIXI(pixiLines)
                  self.renderPIXI(highlightedLine)
                }
              });
              transition(foreground)
                  // .attr("d", path)
                  
              // console.log('drag end', event)
            })
          );

      // Add an axis and title.
      g.append("svg:g")
          .attr("class", "axis")
          .each(function(d) { d3.select(this).call(axis.scale(y[d])); })
        .append("svg:text")
          .attr("text-anchor", "middle")
          .attr("y", -9)
          .text(String)

        // additional 'null' label
        .each(function(d) {
          d3.select(this.parentNode).append("svg:text")
            .attr("text-anchor", "middle")
            .attr("dominant-baseline", "middle") 
            .attr("x", 0) // tick length
            .attr("y", h + nullOffset)
            .text("+");
        })


        // additional 'null' label
        .each(function(d) {
            d3.select(this.parentNode).append("svg:text")
              .attr("text-anchor", "left")
              .attr("dominant-baseline", "middle") 
              .attr("x", -9) // tick length
              .attr("y", h + nullOffset)
              .text("null");
        });

      // Add and store a brush for each axis.
      g.append("svg:g")
          .attr("class", "brush")
          .each(function(d) { 
            d3.select(this).call(y[d].brush = d3.brushY().extent([[-12,0],[24, nullOffset + y[d].range()[0]]]).on("start brush", brush).on("end", brushEnd)); })
      
      function position(d) {
        var v = dragging[d];
        return v == null ? x(d) : v;
      }
      
      // Returns the path for a given data point.
      function path(d) {
        myLine = line(dimensions.map(function(p) { 
          myX = position(p)
          myY = y[p](d[p]) ?? y[p].range()[0]
          // console.log("myX,Y = ", myX, myY)
          return [myX, myY] 
        }));
        // console.log(myLine.toString())
        return myLine;
      }
      
      // function brushStart({event, selection, d}) {
      //   ySelections[d] = null
      // };

      function brushEnd({event, selection}) {
        // console.log("brushEnd")
        // brushing = false
        self.brushing = false;
      };

      // Handles a brush event, toggling the display of foreground lines.
      function brush(event, d) {
        self.brushing = true;
        this.pointerEvents="all"
        // console.log("brush", event.selection, d) // contains dimension and min/max range
        if (event.selection[0] == event.selection[1]) {
          ySelections[d] = null
        } else {
          ySelections[d] = event.selection
        }
        var actives = dimensions.filter(function(z) {
          return ySelections[z];
        })

        // console.log("actives:", actives)

        var extents = {}
        actives.forEach(z => {
          extents[z] = ySelections[z]
        });

        var filter = {};
        actives.forEach(key => {
          // relying on fact that 'ordinal' scales do not have '.unknown' property
          filter[key] = {
            min: extents[key][0],
            max: extents[key][1],
            type: (y[key].unknown) ? "cardinal" : "ordinal",
            scale: y[key]
          }
        });

        model.set({filter: filter});

        for (var key in undisplayable) {
          delete undisplayable[key]
        }

        myData.forEach(function (d) {
          if (actives.every(function(p) {
            myMin = extents[p][0],
            myMax = extents[p][1],
            myVal = y[p](d[p])

            var res = (myMin <= myVal) && (myMax >= myVal)
            return  res;
          })) {
            // console.log("setting undisplayable ", d, "to true")
            delete undisplayable[d["id"]]
          } else {
            // console.log(undisplayable, "setting undisplayable ", d, "to false")
            undisplayable[d["id"]] = true
          }
        })

        self.renderPIXI(pixiLines)
        self.renderPIXI(highlightedLine)
      }
      
      function transition(g) {
        return g.transition().duration(500);
      }

      self.highlight = function(i) {
        if (typeof i === "undefined") {
          highlighted = null
        } else {
          var myId  = model.get('filtered')[i]["id"]
            // got the item thats highlighted
          for (let index = 0; index < myData.length; index++) {
            const element = myData[index];
            if (element["id"] == myId) {
              highlighted = element
              break
            }
          }
        }
        // console.log("highlighted:", highlighted)
        self.renderPIXI(pixiLines)
        self.renderHighlightedPIXI(highlightedLine)

      };

      app.stage.addChild(pixiLines);
      app.stage.addChild(highlightedLine);

    }
    
    return self;
  };
  
})(d3);
