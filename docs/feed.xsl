<?xml version="1.0" encoding="utf-8"?>
<!-- Muestra un feed Atom como página legible cuando se abre en el navegador.
     Los lectores de feeds ignoran esta hoja y leen el XML directamente. -->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:a="http://www.w3.org/2005/Atom">
  <xsl:output method="html" encoding="utf-8" indent="yes"/>

  <xsl:template match="/a:feed">
    <xsl:variable name="direccion" select="a:link[@rel='self']/@href"/>
    <html lang="es">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <meta name="robots" content="noindex"/>
        <title><xsl:value-of select="a:title"/></title>
        <style>
          :root { --fg: #1f2a30; --suave: #5b6770; --fondo: #fff; --caja: #eef3f5; --acento: #1f4e5f; --borde: #d5dde1; }
          @media (prefers-color-scheme: dark) {
            :root { --fg: #e3e8eb; --suave: #a3afb6; --fondo: #1b2226; --caja: #253036; --acento: #8fc3d6; --borde: #36434a; }
          }
          body { margin: 0; background: var(--fondo); color: var(--fg); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
          main { max-width: 44rem; margin: 0 auto; padding: 2rem 1rem 3rem; }
          h1 { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.25rem; }
          .marca { color: var(--suave); font-size: 0.9rem; margin: 0 0 1.5rem; }
          .caja { background: var(--caja); border-radius: 0.4rem; padding: 1rem 1.1rem; margin: 0 0 2rem; }
          .caja p { margin: 0 0 0.6rem; }
          .direccion { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
          code { font: 0.9rem/1.4 ui-monospace, "IBM Plex Mono", monospace; background: var(--fondo); border: 1px solid var(--borde); border-radius: 0.3rem; padding: 0.3rem 0.5rem; overflow-wrap: anywhere; }
          button { font: inherit; font-size: 0.9rem; cursor: pointer; color: #fff; background: var(--acento); border: 0; border-radius: 0.3rem; padding: 0.3rem 0.8rem; }
          @media (prefers-color-scheme: dark) { button { color: #10181c; } }
          a { color: var(--acento); }
          ul { list-style: none; padding: 0; margin: 0; }
          li { border-top: 1px solid var(--borde); padding: 0.8rem 0; }
          .fecha { color: var(--suave); font-size: 0.85rem; }
          .titulo { font-weight: 600; display: block; }
          .vacio { color: var(--suave); }
        </style>
      </head>
      <body>
        <main>
          <h1><xsl:value-of select="a:title"/></h1>
          <p class="marca"><xsl:value-of select="a:author/a:name"/></p>
          <div class="caja">
            <p><strong>Esto es un feed Atom.</strong> Para recibir los avisos, copia esta dirección y añádela a tu lector de feeds (Feedly, Inoreader, NetNewsWire, Thunderbird…):</p>
            <p class="direccion">
              <code id="direccion"><xsl:value-of select="$direccion"/></code>
              <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('direccion').textContent).then(function(){{ event.target.textContent = 'Copiada'; }})">Copiar</button>
            </p>
            <p style="margin:0"><a href="{a:link[@rel='alternate']/@href}">Volver a la web</a></p>
          </div>
          <xsl:choose>
            <xsl:when test="a:entry">
              <ul>
                <xsl:for-each select="a:entry">
                  <li>
                    <span class="fecha"><xsl:value-of select="substring(a:updated, 1, 10)"/></span>
                    <a class="titulo" href="{a:link/@href}"><xsl:value-of select="a:title"/></a>
                    <xsl:value-of select="a:summary"/>
                  </li>
                </xsl:for-each>
              </ul>
            </xsl:when>
            <xsl:otherwise>
              <p class="vacio">Todavía no hay avisos. Cuando se detecte un cambio aparecerá aquí y en tu lector de feeds.</p>
            </xsl:otherwise>
          </xsl:choose>
        </main>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
