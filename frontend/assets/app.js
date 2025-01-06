const submitQuery = (event) => {
  event.preventDefault();
  const {
    location: { search },
  } = window;
  const {
    target: {
      sort: { value: sort },
      query: { value: query },
      direction: { value: direction },
    },
  } = event;

  const url = new URLSearchParams(search);
  url.set("sort", sort);
  url.set("direction", direction);

  if (query.length > 0 && url.get("query") !== query) {
    url.set("query", query);
    url.set("page", "1");
  } else if (query.length === 0 && url.get("query") !== null) {
    url.delete("query");
  }

  window.location.search = url;
};

//admin

const showSearchBar = (fallBack, params) => {
  const { page, sort, direction, query } = params;

  const searchForm = document.getElementById("search-form");
  searchForm.style.display = "flex";

  checkAndRedirect([page, sort, direction], fallBack);

  document.querySelector("[name='query']").value = query;
  document.querySelector("[name='direction']").value = direction;
  document.querySelector("[name='sort']").value = sort;
};

const putTableHeaders = (headers, header, tableBody) => {
  headers.forEach((value) => {
    const newHeader = element("td");
    newHeader.innerText = value;
    header.appendChild(newHeader);
  });
  tableBody.appendChild(header);
};

const renderAdminView = async () => {
  const {
    location: { search },
  } = window;
  const url = new URLSearchParams(search);

  const view = url.get("view");
  checkAndRedirect([view], "?view=add");

  document.getElementById(view + "-radio").checked = true;
  const viewDiv = document.getElementById("admin-view");
  const viewParams = ({ page, sort, direction, query } = albumParams(url));

  switch (view) {
    case "add":
      const [manageArtist, mangeAlbum, br] = elements(["a", "a", "br"]);
      manageArtist.innerText = "Add an artist";
      manageArtist.setAttribute("href", "/admin/manage-artist?action=new");
      mangeAlbum.innerText = "Add an album";
      mangeAlbum.setAttribute("href", "/admin/manage-album?action=new");
      [manageArtist, br, mangeAlbum].forEach((element) => {
        viewDiv.appendChild(element);
      });
      break;

    case "artists":
      {
        const [nameOption, modifiedOption] = elements(["option", "option"]);
        nameOption.innerHTML = nameOption.value = "name";
        modifiedOption.innerHTML = modifiedOption.value = "modified";
        const sortInput = document.querySelector("[name=sort]");
        sortInput.replaceChildren(nameOption, modifiedOption);

        showSearchBar(
          "?view=artists&page=1&sort=name&direction=ascending",
          viewParams
        );

        const searchParam = query === null ? "" : `&query=${query}`;
        const apiUrl = `/api/admin/artists?page=${page}&sort=${sort}&direction=${direction}${searchParam}`;
        const response = await fetch(apiUrl);
        const { artists, pages } = await response.json();

        const [table, tableBody, header] = elements(["table", "tbody", "tr"]);
        putTableHeaders(
          ["name", "biography", "modified", "albums"],
          header,
          tableBody
        );
        table.classList.add("dispatched-table");

        artists.forEach((artist) => {
          const artistCopy = { ...artist };
          delete artistCopy.artist_id;

          const newRow = element("tr");
          Object.keys(artistCopy).forEach((key) => {
            const newCell = element("td");
            switch (key) {
              case "name":
                const editLink = element("a");
                editLink.setAttribute(
                  "href",
                  `manage-artist?action=edit&artist_id=${artist["artist_id"]}`
                );
                editLink.innerText = artist[key];
                newCell.appendChild(editLink);
                break;
              case "modified":
                const utcDate = new Date(`${artist[key]} UTC`);
                newCell.innerText = utcToLocale(utcDate);
                break;
              default:
                newCell.innerText = artist[key];
                break;
            }

            newRow.appendChild(newCell);
          });
          tableBody.appendChild(newRow);
        });

        table.appendChild(tableBody);
        viewDiv.appendChild(table);

        renderPages(pages, sort, direction, searchParam, "artists");
      }
      break;

    case "albums":
      {
        showSearchBar(
          "?view=albums&page=1&sort=modified&direction=descending",
          viewParams
        );

        const searchParam = query === null ? "" : `&query=${query}`;
        const apiUrl = `/api/albums?page=${page}&sort=${sort}&direction=${direction}${searchParam}`;
        const response = await fetch(apiUrl);
        const { albums, pages } = await response.json();

        const [table, tableBody, header] = elements(["table", "tbody", "tr"]);
        putTableHeaders(
          [
            "photo",
            "title",
            "name",
            "stock",
            "release year",
            "price",
            "modified",
          ],
          header,
          tableBody
        );
        table.classList.add("dispatched-table");

        albums.forEach((album) => {
          const albumCopy = { ...album };
          delete albumCopy.artist_id;

          const newRow = element("tr");
          Object.keys(albumCopy).forEach((key) => {
            const newCell = element("td");
            switch (key) {
              case "photo":
                const image = element("img");
                image.src = `/common/${album[key]}`;
                image.classList.add("table-img");
                newCell.appendChild(image);
                break;
              case "title":
                const editLink = element("a");
                editLink.setAttribute(
                  "href",
                  `manage-album?action=edit&album=${toUrlCase(
                    album[key]
                  )}&artist_id=${album["artist_id"]}`
                );
                editLink.innerText = album[key];
                newCell.appendChild(editLink);
                break;
              case "modified":
                const utcDate = new Date(`${album[key]} UTC`);
                newCell.innerText = utcToLocale(utcDate);
                break;
              default:
                newCell.innerText = album[key];
                break;
            }

            newRow.appendChild(newCell);
          });
          tableBody.appendChild(newRow);
        });
        table.appendChild(tableBody);
        viewDiv.appendChild(table);

        renderPages(pages, sort, direction, searchParam, "albums");
      }
      break;
  }
};

const renderPages = (pages, sort, direction, searchParam, view = null) => {
  const firstParam = view !== null ? `view=${view}&` : "";

  const pageDiv = document.getElementById("pages");
  pageDiv.style.display = "block";

  [...Array(pages).keys()].forEach((dbPage) => {
    const htmlRef = dbPage + 1;
    const pageUrl = `?${firstParam}page=${htmlRef}&sort=${sort}&direction=${direction}${searchParam}`;
    const anchor = element("a");
    anchor.setAttribute("href", pageUrl);
    anchor.innerHTML = htmlRef;
    pageDiv.appendChild(anchor);
    if (htmlRef !== pages) {
      pageDiv.append(",");
    }
  });
};

const utcToLocale = (date) => {
  const year = date.getFullYear();
  const day = date.getDate();
  const month = date.getMonth() + 1;
  return `${day}.${month}.${year} ${date.toTimeString().substring(0, 5)}`;
};

const renderArtistForm = async () => {
  const {
    location: { search },
  } = window;
  const url = new URLSearchParams(search);
  const action = url.get("action");
  checkAndRedirect([action], "?action=new");
  const h1 = document.getElementById("manange-artist-title");

  switch (action) {
    case "edit":
      const artistName = url.get("artist_id");
      checkAndRedirect([artistName], "?action=new");
      const response = await fetch(`/api/artists/${artistName}?view=admin`);
      const {
        artist: { name, bio, artist_id },
      } = await response.json();
      document.getElementById("existing-artist-id").value = artist_id;
      document.querySelector("[name=bio]").value = bio;
      document.querySelector("[name=name]").value = name;
      h1.innerHTML = `Edit artist ${name}`;

      const actionGroup = document.querySelector(".action-group");
      const deleteButton = element("button");
      deleteButton.setAttribute("type", "button");
      deleteButton.onclick = () => {
        deleteArtist(artist_id);
      };
      deleteButton.innerText = "Delete";
      actionGroup.appendChild(deleteButton);
      break;
    case "new":
      h1.innerHTML = `Create a new artist`;
      break;
  }

  document.getElementById(action + "-radio").checked = true;
};

const deleteArtist = async (artist_id) => {
  const deletePrompt = prompt(
    "are you sure you want to delete this artist? type 'yes' or 'no'"
  );
  if (deletePrompt.trim() == "yes") {
    const response = await fetch(`/api/admin/artists/${artist_id}`, {
      method: "Delete",
    });
    const { status } = response;
    const { detail } = await response.json();
    alert(detail);
    status === 200 &&
      window.location.replace(
        "/admin/?view=artists&page=1&sort=modified&direction=descending"
      );
  }
};

const sendAlbum = async (event) => {
  event.preventDefault();
  const fieldSet = document.querySelector("fieldset");
  const currentForm = new FormData(event.target);
  fieldSet.disabled = true;

  for (var pair of currentForm.entries()) {
    if (typeof pair[1] === "string") {
      currentForm.set(pair[0], pair[1].trim());
    }
  }

  const response = await fetch("/api/admin/albums", {
    method: "POST",
    body: currentForm,
  });
  const { status } = response;
  const { detail, artist_id, title } = await response.json();
  fieldSet.disabled = false;

  alert(detail);

  if (status === 200 && title !== undefined && artist_id !== undefined) {
    window.location.search = `?action=edit&album=${toUrlCase(
      title
    )}&artist_id=${artist_id}`;
  }
};

const sendArtist = async (event) => {
  event.preventDefault();
  const currentForm = new FormData(event.target);
  const fieldSet = document.querySelector("fieldset");
  fieldSet.disabled = true;

  for (var pair of currentForm.entries()) {
    if (typeof pair[1] === "string") {
      currentForm.set(pair[0], pair[1].trim());
    }
  }

  const response = await fetch("/api/admin/artists", {
    method: "POST",
    body: currentForm,
  });
  const { status } = response;
  const { detail, artist_id } = await response.json();
  fieldSet.disabled = false;

  alert(detail);

  if (status === 200 && name !== undefined) {
    const urlParams = `?action=edit&artist_id=${artist_id}`;
    window.location.search = urlParams;
  }
};

const renderAlbumForm = async () => {
  const {
    location: { search },
  } = window;
  const url = new URLSearchParams(search);

  const action = url.get("action");
  checkAndRedirect([action], "?action=new");

  const response = await fetch("/api/admin/artists");
  const { artists } = await response.json();
  const artistSelect = document.querySelector("[name=artist_id]");
  artists.forEach((artist) => {
    const { name, artist_id } = artist;
    const newOption = element("option");
    newOption.innerHTML = name;
    newOption.value = artist_id;
    artistSelect.appendChild(newOption);
  });

  const h1 = document.getElementById("manange-album-title");

  switch (action) {
    case "edit":
      const albumParam = url.get("album");
      const artistID = url.get("artist_id");
      checkAndRedirect([albumParam, artistID], "?action=new");
      const {
        album: { name, photo, title, artist_id, album_id },
        album,
        songs,
      } = await fetch(`/api/artists/${artistID}/album/${albumParam}`).then(
        (response) => response.json()
      );

      h1.innerText = `Edit ${title} by ${name}`;
      document.getElementById("existing-album-id").value = album_id;

      ["title", "release_year", "price"].forEach((key) => {
        const input = document.querySelector(`[name=${key}]`);
        input.value = input.placeholder = album[key];
      });

      const existingOption = Array.from(
        artistSelect.querySelectorAll("option")
      ).find((option) => Number(option.value) === artist_id);

      artistSelect.value = existingOption.value;

      const img = document.getElementById("photo-preview");
      const imgInput = document.getElementById("photo");

      const imgData = await fetch(`/common/${photo}`).then((response) =>
        response.blob()
      );

      const existingFile = new File([imgData], photo);
      const dataXfer = new DataTransfer();
      dataXfer.items.add(existingFile);
      imgInput.files = dataXfer.files;
      img.src = URL.createObjectURL(existingFile);

      const [songOne, durationOne] = Array.from(
        document.querySelectorAll("[name=song_1],[name=duration_1]")
      );
      const firstSong = songs[0];
      songOne.value = firstSong.song;
      durationOne.value =
        firstSong.duration !== null ? toMMSS(firstSong.duration) : "";

      Object.keys(songs).forEach((track, n) => {
        n !== 0 && addSong(songs[track]);
      });

      const actionGroup = document.querySelector(".action-group");
      const deleteButton = element("button");
      deleteButton.setAttribute("type", "button");
      deleteButton.onclick = () => {
        deleteAlbum(album_id);
      };
      deleteButton.innerText = "Delete";
      actionGroup.appendChild(deleteButton);

      break;
    case "new":
      h1.innerText = "Create a album";
      break;
  }

  document.getElementById(action + "-radio").checked = true;
};

const deleteAlbum = async (album_id) => {
  const deletePrompt = prompt(
    "are you sure you want to delete this album? type 'yes' or 'no'"
  );
  if (deletePrompt.trim() == "yes") {
    const response = await fetch(`/api/admin/albums/${album_id}`, {
      method: "Delete",
    });
    const { status } = response;
    const { detail } = await response.json();
    alert(detail);
    status === 200 &&
      window.location.replace(
        "/admin/?view=albums&page=1&sort=modified&direction=descending"
      );
  }
};

const albumParams = (url) => {
  const page = url.get("page"),
    sort = url.get("sort"),
    direction = url.get("direction"),
    query = url.get("query");

  return { page, sort, direction, query };
};

const checkAndRedirect = (params, fallBack) => {
  const shouldRedirect = params.some((param) => param === null);
  if (shouldRedirect) {
    window.location.search = fallBack;
    throw false;
  }
};

const changeView = async (event) => {
  const {
    target: { value: view },
  } = event;

  let urlParams = "";

  switch (view) {
    case "add":
      urlParams = "?view=add";
      break;
    case "albums":
      urlParams = "?view=albums&page=1&sort=modified&direction=descending";
      break;
    case "artists":
      urlParams = "?view=artists&page=1&sort=modified&direction=descending";
      break;
  }

  window.location.search = urlParams;
};

const checkTime = (event) => {
  const { ctrlKey, key, keyCode } = event;

  const number = parseInt(key);
  const validNavigation = [46, 8, 116, 37, 39].includes(keyCode);
  const validControl = ctrlKey && ["a", "p", "c", "x", "z", "v"].includes(key);

  if (!isNaN(number) || key === ":" || validControl || validNavigation) {
    return true;
  } else {
    event.preventDefault();
  }
};

const auth = async (event) => {
  event.preventDefault();
  const {
    target: {
      username: { value: username },
      password: { value: password },
    },
  } = event;

  const {
    location: { pathname },
  } = window;

  const apiUrl = pathname === "/register" ? pathname : "/sign-in";

  const url = `/api${apiUrl}`;

  const response = await fetch(url, {
    body: JSON.stringify({ username: username, password: password }),
    method: "POST",
  });

  const { status } = response;
  const { detail } = await response.json();
  alert(detail);

  status === 200 && window.location.replace("/");
};

const removeSong = () => {
  const tbody = document.getElementById("songs").querySelector("tbody");

  if (tbody.children.length > 2) {
    const lastTrack = Array.from(tbody.children)[tbody.children.length - 1];
    lastTrack.remove();
  } else {
    alert("need at least one track");
  }
};

const addSong = (track = null) => {
  const tbody = document.getElementById("songs").querySelector("tbody");

  if (tbody.children.length <= 20) {
    const lastTrack = Array.from(tbody.children)[
      tbody.children.length - 1
    ].cloneNode(true);
    lastTrack.removeAttribute("id");

    Array.from(lastTrack.children).forEach((child) => {
      const input = child.children[0];
      const [inputName, inputNumber] = input.name.split("_");
      const hasTrack = track !== null;

      switch (inputName) {
        case "song":
          input.value = "";
          if (hasTrack && track.hasOwnProperty("song")) {
            input.value = track.song;
          }
          break;
        case "duration":
          input.value = "";
          if (hasTrack && track.hasOwnProperty("duration")) {
            input.value = track.duration !== null ? toMMSS(track.duration) : "";
          }
          break;
        case "track":
          const { value } = input;
          input.value = String(Number(value) + 1);
          break;
      }
      input.name = inputName + "_" + String(Number(inputNumber) + 1);
    });
    tbody.appendChild(lastTrack);
  } else {
    alert("too many tracks");
  }
};

const toMMSS = (duration) => {
  const mmSS = new Date(duration * 1000).toISOString().slice(14, 19);
  return mmSS.substring(0, 1) === "0" ? mmSS.slice(1, 5) : mmSS;
};

const addPhoto = (event) => {
  const photo = event.target.files[0];

  const img = document.getElementById("photo-preview");
  img.src = URL.createObjectURL(photo);
};

const renderOrders = async () => {
  const response = await fetch("/api/orders");
  const { orders, cart } = await response.json();

  console.log(orders, cart);

  const targetDiv = document.getElementById("details");
  const hasCart = cart.balance !== null && cart.albums !== null;

  if (hasCart) {
    const { albums, balance } = cart;
    const [cartHeader, orderBtn, balanceP] = elements(["h2", "button", "p"]);
    cartHeader.innerText = "Cart";
    balanceP.innerText = `balance: ${balance}`;
    const table = renderAlbumTable(albums);
    orderBtn.id = "order-button";
    orderBtn.innerText = "Checkout order";
    orderBtn.onclick = () => {
      checkOut();
    };

    [cartHeader, balanceP, table, orderBtn].forEach((element) => {
      targetDiv.appendChild(element);
    });
  }

  if (hasCart && orders.length > 0) {
    const lineBr = element("hr");
    targetDiv.appendChild(lineBr);
  }

  if (orders.length === 0 && !hasCart) {
    const orderHeader = element("h2");
    orderHeader.innerText = "Your cart is empty";
    targetDiv.appendChild(orderHeader);
  }

  if (orders.length > 0) {
    const orderHeader = element("h2");
    orderHeader.innerText = "Dispatched orders";
    targetDiv.appendChild(orderHeader);

    orders.forEach((order) => {
      Object.keys(order)
        .filter((item) => ["order_id", "dispatched", "balance"].includes(item))
        .forEach((key) => {
          const paragraph = element("p");
          paragraph.innerText = `${key.split("_").join(" ")}: ${
            key === "dispatched" && order[key] !== null
              ? new Date(order[key]).toLocaleString()
              : order[key]
          }`;
          targetDiv.appendChild(paragraph);
        });

      const { albums } = order;

      const table = renderAlbumTable(albums);
      targetDiv.appendChild(table);
    });
  }
};

const checkOut = async () => {
  const request = await fetch("/api/cart/checkout", { method: "POST" });

  const { status } = request;
  const { detail } = await request.json();

  if (status === 200) {
    alert(detail);
    location.reload();
  }
};

const renderAlbumTable = (albums) => {
  const [table, tableBody, header] = elements(["table", "tbody", "tr"]);

  putTableHeaders(
    ["cover", "title", "artist", "quantity", "price"],
    header,
    tableBody
  );

  table.classList.add("dispatched-table");
  table.appendChild(tableBody);

  albums.forEach((album) => {
    const row = element("tr");
    const albumCopy = { ...album };
    delete albumCopy.artist_id;

    Object.keys(albumCopy).forEach((key) => {
      const td = element("td");
      switch (key) {
        case "artist":
        case "title":
          const tdA = element("a");
          let albumUri = "";

          if (key === "artist") {
            albumUri += `/artist/${album["artist_id"]}/${toUrlCase(
              album["artist"]
            )}`;
          } else if (key === "title") {
            albumUri += `/artist/${album["artist_id"]}/${toUrlCase(
              album["artist"]
            )}/album/${toUrlCase(album["title"])}`;
            const hiddenA = element("a");
            hiddenA.setAttribute("class", "hideable-path");
            hiddenA.setAttribute("href", albumUri);
            hiddenA.innerText = `${album["artist"]} - ${album["title"]} = ${
              album["price"]
            } x ${album["quantity"]} = ${album["price"] * album["quantity"]}`;
            td.appendChild(hiddenA);
          }

          tdA.setAttribute("href", albumUri);
          tdA.setAttribute("class", "inverse-hideable-path ");
          tdA.innerText = album[key];
          td.appendChild(tdA);

          break;
        case "photo":
          const image = element("img");
          image.src = `/common/${album[key]}`;
          image.classList.add("table-img");
          td.appendChild(image);
          break;
        case "artist_id":
          break;
        default:
          td.innerText = album[key];
      }
      row.appendChild(td);
    });
    tableBody.appendChild(row);
  });

  return table;
};

const renderArtist = async () => {
  const {
    location: { pathname },
  } = window;

  const artist_id = pathname.split("/")[2];
  const url = `/api/artists/${artist_id}?view=user`;
  const response = await fetch(url);
  const {
    artist: { name, albums, bio },
  } = await response.json();

  const h1 = document.querySelector("h1");
  h1.innerText = name;
  const artistP = document.getElementById("bio");
  artistP.innerText = bio;

  renderAlbumTiles(albums);
};

const renderAlbums = async () => {
  const {
    location: { search },
  } = window;
  const url = new URLSearchParams(search);
  const viewParams = ({ page, sort, direction, query } = albumParams(url));

  showSearchBar("?page=1&sort=name&direction=ascending", viewParams);

  const searchParam = query === null ? "" : `&query=${query}`;
  const fetchUrl = `/api/albums?page=${page}&sort=${sort}&direction=${direction}${searchParam}`;

  const { albums, pages } = await fetch(fetchUrl).then((response) =>
    response.json()
  );

  renderAlbumTiles(albums);

  renderPages(pages, sort, direction, searchParam);
};

const renderAlbum = async () => {
  const {
    location: { pathname },
  } = window;

  const noSpaces = pathname.replace(/%20/g, " ");
  const album_title = noSpaces.match(/(?<=album\/).*/)[0];
  const artist_id = noSpaces.match(/(?<=artist\/)\d+(?=\/.*\/album)/)[0];

  console.log(artist_id, album_title);

  const response = await fetch(
    `/api/artists/${artist_id}/album/${album_title}?cart=get`
  );
  const { album, songs, cart } = await response.json();

  document.title += ` ${album.name} - ${album.title}`;

  const [salesBtn, artistA] = elements(["button", "a"]);

  const image = document.getElementById("album-img");

  image.src = `/common/${album.photo}`;
  image.classList.add("album-img");

  const infoDiv = document.getElementById("info-div");

  const paragraphs = Object.keys(album)
    .filter((info) => !["photo", "cart"].includes(info))
    .map((info) => {
      const text = info.split("_").join(" ");
      const paragraph = element("p");
      paragraph.classList.add("album-p");

      switch (info) {
        case "album_id":
        case "artist_id":
          break;
        case "name":
          paragraph.innerText = `${text}: `;
          artistA.setAttribute(
            "href",
            `/artist/${album["artist_id"]}/${toUrlCase(album[info])}`
          );
          artistA.innerText = album[info];
          paragraph.appendChild(artistA);
          break;
        case "stock":
          const span = element("span");
          span.innerText = album[info];
          span.id = "stock-p";
          paragraph.innerText = `${text}: `;
          paragraph.appendChild(span);
          break;
        default:
          paragraph.innerText = `${text}: ${album[info]}`;
          break;
      }

      return paragraph;
    });

  paragraphs.reverse().forEach((item) => {
    infoDiv.prepend(item);
  });

  const table = document.getElementById("songs-table");

  songs.forEach((dbSong) => {
    const row = element("tr");
    Object.keys(dbSong).forEach((item) => {
      if (dbSong[item] !== null) {
        let text = "";
        switch (item) {
          case "track":
            text = `${dbSong[item]}. `;
            break;
          case "duration":
            const slice = dbSong[item] >= 600 ? 14 : 15;
            text = `${new Date(dbSong[item] * 1000)
              .toISOString()
              .slice(slice, 19)}`;
            break;
          case "song":
            text = `${dbSong[item]}`;
            break;
        }
        const td = element("td");
        td.innerText = text;
        row.appendChild(td);
      }
    });

    table.appendChild(row);
  });

  if (cart !== undefined) {
    const [cartInfo, removeBtn] = elements(["i", "button"]);

    cartInfo.id = "cart-info";
    cartInfo.style.display = "block";
    salesBtn.id = "buy-album";
    salesBtn.innerText = "Add to cart";
    removeBtn.id = "remove-button";
    removeBtn.innerText = "Remove from cart";
    removeBtn.style.display = "none";

    if (album.stock <= 0) {
      salesBtn.disabled = true;
      salesBtn.classList.add("disabled-button");
    }

    salesBtn.onclick = () => {
      buyAlbum(album.album_id);
    };

    removeBtn.onclick = () => {
      removeAlbum(album.album_id);
    };

    if (cart > 0) {
      cartInfo.innerText = `${cart} of these albums are in your cart.`;
      removeBtn.style.display = "inline-block";
    }

    [salesBtn, removeBtn, cartInfo].forEach((element) => {
      infoDiv.appendChild(element);
    });
  }
};

const renderAuthForm = () => {
  const {
    location: { pathname },
  } = window;

  let h1text = "";
  switch (pathname) {
    case "/register":
      h1text = "Register as new user";
      break;
    default:
      h1text = "Sign In";
      const nodes = ["a", "br"].map((tag) => element(tag));
      const anchor = nodes.find((node) => node.tagName === "A");
      anchor.setAttribute("href", "/register");
      anchor.innerText = "don't have an account? sign up!";
      const form = document.getElementById("form_id");
      nodes.forEach((node) => {
        form.after(node);
      });
      break;
  }

  //document.querySelector("h1").innerHTML = h1text;
};

//misc functions

const elements = (params) => {
  return params.map((param) => document.createElement(param));
};

const element = (param) => {
  return document.createElement(param);
};

const createElements = (tags) => {
  const tagsObj = {};
  tags.forEach((tag) => {
    const { name, type } = tag;
    tagsObj[name] = document.createElement(type);
  });
  return tagsObj;
};

const renderAlbumTiles = (albums) => {
  const albumsDiv = document.getElementById("albums");
  albums.forEach((album) => {
    const { title, name, photo, artist_id } = album;

    const [targetDiv, anchor, image] = elements(["div", "a", "img"]);

    const paragraphs = Object.keys(album)
      .filter((info) => ["release_year", "stock", "price"].includes(info))
      .map((info) => {
        const text = info.split("_").join(" ");
        const paragraph = element("p");
        paragraph.classList.add("album-p");
        paragraph.innerText = `${text}: ${album[info]}`;
        return paragraph;
      });

    targetDiv.classList.add("albums-div");
    const albumUri = `/artist/${artist_id}/${toUrlCase(name)}/album/${toUrlCase(
      title
    )}`;
    anchor.setAttribute("href", albumUri);
    anchor.innerText = `${name} - ${title}`;
    image.src = `/common/${photo}`;
    image.classList.add("albums-img");

    [image, anchor, ...paragraphs].forEach((item) => {
      targetDiv.appendChild(item);
    });

    albumsDiv.appendChild(targetDiv);
  });
};

const toUrlCase = (value) => {
  return encodeURIComponent(value.toLowerCase().replace(/\s/g, "-"));
};

const logOut = () => {
  document.cookie = "token=; Max-Age=0; path=/; domain=" + location.host;
};

//fetches

const removeAlbum = async (album_id) => {
  const removeBtn = document.getElementById("remove-button");
  removeBtn.disabled = true;

  const response = await fetch(`/api/cart/${album_id}/remove`, {
    method: "POST",
  });

  const { status } = response;
  const { remaining, cart } = await response.json();

  switch (status) {
    case 200:
      const stockP = document.getElementById("stock-p");
      stockP.innerText = String(remaining);
      const salesBtn = document.getElementById("buy-album");
      const cartInfo = document.getElementById("cart-info");
      cartInfo.innerText =
        cart <= 0 ? "" : `${cart} of these albums are in your cart.`;
      salesBtn.classList.remove("disabled-button");

      if (cart === 0) {
        removeBtn.style.display = "none";
      }

      if (remaining > 0) {
        salesBtn.disabled = false;
      }

      removeBtn.disabled = false;
      alert("this album has been removed from your cart");
  }
};

const buyAlbum = async (album_id) => {
  const salesBtn = document.getElementById("buy-album");
  salesBtn.disabled = true;

  const response = await fetch(`/api/cart/${album_id}/add`, {
    method: "POST",
  });

  const { status } = response;
  const { remaining, cart } = await response.json();

  switch (status) {
    case 200:
      const stockP = document.getElementById("stock-p");
      stockP.innerText = String(remaining);
      const removeBtn = document.getElementById("remove-button");
      const cartInfo = document.getElementById("cart-info");
      cartInfo.innerText = `${cart} of these albums are in your cart.`;
      removeBtn.style.display = "inline-block";

      if (remaining === 0) {
        salesBtn.classList.add("disabled-button");
      } else {
        salesBtn.disabled = false;
      }

      alert("this album has been added to your cart");
      break;
  }
};

const renderUser = async () => {
  const request = await fetch(`/api/user`);
  const { user } = await request.json();
  const targetDiv = document.getElementById("details");

  Object.keys(user)
    .filter((detail) => detail !== "orders" && detail !== "cart")
    .forEach((param) => {
      const pElement = element("p");
      if (param.includes("created")) {
        pElement.innerText = `${param}: ${user[param].substring(0, 10)} ${user[
          param
        ].substring(11, 16)}`;
      } else {
        pElement.innerText = `${param}: ${user[param]}`;
      }

      targetDiv.appendChild(pElement);
    });

  const { orders, cart } = user;

  if (orders > 0 || cart > 0) {
    const existingHref = document.getElementById("log-out");
    const [newHref, newLine] = elements(["a", "br"]);
    const ordersString = orders > 0 ? `${orders} order(s) dispatched.` : "";
    const cartString = cart > 0 ? `${cart} albums in cart.` : "";

    newHref.setAttribute("href", "/my-account/orders");
    newHref.innerText = `Your orders: ${ordersString} ${cartString}`;
    newHref.classList.add("action-link");

    existingHref.insertAdjacentElement("afterend", newHref);
    existingHref.insertAdjacentElement("afterend", newLine);
  }
};
