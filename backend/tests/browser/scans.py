"""Page-side scripts the browser tests share.

A dash can be drawn as well as typed. ace shows no em dash anywhere, and
a short rule painted before a word with CSS reads as one exactly as a
typed character does, which is how a bar before "BIG TECH" got past a
guard that only reads text. This finds them by what they look like.
"""

# What counts as a drawn dash: a visible, inked box 6 to 40px wide and
# at most 3px tall, from a pseudo-element or an element. Progress bars
# and dividers are wider, dots and rails are taller, so neither trips it.
# The fill inside a progress track is the one exception, because its
# width is the value it shows (a 43% match is 36px of an 84px track).
# Pseudo-element content holding a dash character is reported as well.
_SCAN = r"""
function(doc){
  var win = doc.defaultView;
  var found = [];
  var TYPED = /[\u2012-\u2015\u2212]/;
  function shown(r, cs){
    return r.width > 0 && r.height > 0 && cs.display !== 'none'
      && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0;
  }
  function shortBar(w, h){ return w >= 6 && w <= 40 && h > 0 && h <= 3; }
  function inked(cs){
    return (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent')
      || cs.backgroundImage !== 'none'
      || parseFloat(cs.borderTopWidth) > 0
      || parseFloat(cs.borderBottomWidth) > 0;
  }
  function name(el){
    var c = typeof el.className === 'string' ? el.className.trim() : '';
    return el.tagName.toLowerCase() + (c ? '.' + c.split(/\s+/).join('.') : '');
  }
  var all = doc.querySelectorAll('body *');
  for (var i = 0; i < all.length; i++){
    var el = all[i];
    if (el.closest('svg')) continue;
    var cs = win.getComputedStyle(el);
    var r = el.getBoundingClientRect();
    var pr = el.parentElement ? el.parentElement.getBoundingClientRect() : null;
    var fill = pr !== null && pr.height <= 6 && pr.width > r.width;
    if (!fill && shown(r, cs) && shortBar(r.width, r.height) && inked(cs))
      found.push(name(el) + ' is a ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' bar');
    ['::before', '::after'].forEach(function(p){
      var ps = win.getComputedStyle(el, p);
      var c = ps.content;
      if (!c || c === 'none' || c === 'normal') return;
      if (TYPED.test(c)) found.push(name(el) + p + ' holds a dash character');
      var w = parseFloat(ps.width), h = parseFloat(ps.height);
      if (ps.display !== 'none' && shortBar(w, h) && inked(ps))
        found.push(name(el) + p + ' is drawn as a ' + w + 'x' + h + ' bar');
    });
  }
  return found;
}
"""


def drawn_dash_scan(
    document: str = "document",
) -> str:
    """JavaScript that returns a list of drawn dashes in a document.

    ``document`` is an expression for the document to scan, so the same
    scan covers the app and an extension page loaded into a frame.
    """

    return "(" + _SCAN + ")(" + document + ")"
