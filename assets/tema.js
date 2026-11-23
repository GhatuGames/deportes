/* aplica el tema guardado antes de pintar (evita parpadeo) */
(function () { try { var t = localStorage.getItem('gd_tema'); if (t === 'claro' || t === 'oscuro') document.documentElement.setAttribute('data-tema', t); } catch (e) {} })();
