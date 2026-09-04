<div align="center">

<!-- Portrait: skipped for now. To add one later:
     python3 scripts/make_portrait.py photo.png --crop L,T,R,B
     python3 scripts/embed_portrait_font.py
     then: <img src="./ascii.svg" width="460" alt="Julius Young III"/> -->

# Julius Young III

<img src="./stats.svg" width="620" alt="Contributions in the last year"/>

<!-- populates on the first run of the stats workflow -->

[velocitydemos.com](https://velocitydemos.com) &nbsp;·&nbsp;
[instagram](https://www.instagram.com/juliusxyoung/) &nbsp;·&nbsp;
[linkedin](https://www.linkedin.com/in/juliusy3/) &nbsp;·&nbsp;
[email](mailto:julius@velocitydemos.com)

</div>

<img src="./hd-about.svg" width="620" alt="about"/>

> Building a world of my own.

<!-- Add stack and projects sections when you're ready. Template:

<img src="./hd-stack.svg" width="620" alt="stack"/>

<samp>lang &nbsp; lang &nbsp; framework &nbsp; tool</samp>

<img src="./hd-projects.svg" width="620" alt="projects"/>

**[repo-name](https://github.com/ypc-ux/repo-name)** &nbsp;·&nbsp; <samp>lang</samp><br>
One line on what it does.
-->

<img src="./hd-stats.svg" width="620" alt="stats"/>

<div align="center">

<img src="./streak.svg" width="620" alt="Current and longest streak"/>

<img src="./langs.svg" width="620" alt="Top languages by bytes and by repo"/>

<img src="./year.svg" width="620" alt="The last year, one character per day"/>

</div>

<img src="./hd-about-this-page.svg" width="620" alt="about this page"/>

Every graphic here is generated, not embedded from anyone else's server.<br>
The stat graphics and these section headings are drawn by<br>
[a scheduled action](.github/workflows/stats.yml) straight from the GitHub GraphQL<br>
API, once a day, committing only what changed.

They animate with SMIL inside the SVG, because GitHub strips scripts from<br>
READMEs — and since nothing loads from a third party, nothing here can<br>
rate-limit or go dark. The headings are SVGs for the same reason: GitHub also<br>
strips CSS, so an image is the only way to put this page's own typeface on them.

The typeface is [JetBrains Mono](scripts/fonts), subset to just the characters<br>
each graphic draws and inlined as base64.

Language totals cover public repositories only. `year.svg` uses a<br>
character ramp: `:` `+` `#` `@`, quiet to loud.
