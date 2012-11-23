(function($) {
  var DAY, HOUR, MINUTE, SECOND, apiErrorHandler, defaultView, formatTime, showMessage;
  defaultView = "main";
  showMessage = function($messageEl, message) {
    return $messageEl.html(message);
  };
  apiErrorHandler = function($errorEl, xhr) {
    var errorMessage, errorResult;
    errorMessage = "";
    try {
      errorResult = $.parseJSON(xhr.responseText);
      errorMessage = errorResult.error;
    } catch (e) {
      errorMessage = xhr.responseText;
      if (!errorMessage) {
        errorMessage = "Error: " + xhr.status;
      }
    }
    return showMessage($errorEl, errorMessage);
  };
  SECOND = 1000;
  MINUTE = SECOND * 60;
  HOUR = MINUTE * 60;
  DAY = HOUR * 24;
  formatTime = function(time, now) {
    var answer, delta;
    if (typeof time === "number") {
      time = new Date(time);
    }
    if (now) {
      if (typeof now === "number") {
        now = new Date(now);
      }
    } else {
      now = new Date;
    }
    answer = "";
    delta = now.getTime() - time.getTime();
    if (delta < 0) {
      answer = "now";
    } else if (delta < MINUTE) {
      answer = "" + (delta / SECOND).toFixed(0) + "s ago";
    } else if (delta < HOUR) {
      answer = "" + (delta / MINUTE).toFixed(0) + "m ago";
    } else if (delta < DAY) {
      answer = "" + (time.getHours()) + ":" + (time.getMinutes());
    } else if (delta < (DAY * 31)) {
      answer = "This month";
    } else {
      answer = "Long ago";
    }
    return answer;
  };
  window.Contact = Backbone.Model.extend({
    defaults: function() {
      return {
        name: '',
        phoneNumber: '',
        subscribed: false,
        isDefaultSender: false
      };
    }
  });
  window.Contacts = Backbone.Collection.extend({
    model: Contact,
    url: '/api/admin/contacts'
  });
  window.LogEntry = Backbone.Model.extend({});
  window.LogEntries = Backbone.Collection.extend({
    model: LogEntry,
    url: '/api/admin/log',
    parse: function(response) {
      this.serverTime = new Date(response.now);
      return response.logItems;
    }
  });
  window.LoginView = Backbone.View.extend({
    events: {
      'click .loginButton': 'login',
      'keypress input': 'loginOnEnter'
    },
    initialize: function() {
      _.bindAll(this, "render");
      return this.template = _.template($('#login-template').html());
    },
    render: function() {
      var renderedContent;
      renderedContent = this.template;
      $(this.el).html(renderedContent);
      return this;
    },
    loginOnEnter: function(event) {
      if (event.keyCode === 13) {
        return this.login(event);
      }
    },
    login: function(event) {
      var self;
      event.preventDefault();
      self = this;
      return $.ajax({
        type: 'POST',
        url: '/api/login',
        data: 'password=' + this.$('.password').val(),
        success: function() {
          return window.app.navigate(defaultView, true);
        },
        error: function(xhr, textStatus, errorThrown) {
          return apiErrorHandler(self.$('.errorText'), xhr);
        }
      });
    }
  });
  window.ContactView = Backbone.View.extend({
    tagName: 'li',
    className: 'listItem selectable',
    initialize: function() {
      _.bindAll(this, "render");
      this.template = _.template($('#contact-template').html());
      return this.model.on('change', this.render);
    },
    render: function() {
      var renderedContent;
      renderedContent = this.template(this.model.toJSON());
      $(this.el).html(renderedContent);
      return this;
    }
  });
  window.ContactEditorContactView = window.ContactView.extend({
    events: {
      'click': 'clicked'
    },
    selected: false,
    clicked: function() {
      this.selected = !this.selected;
      this.trigger('selectionChanged', this.selected);
      if (this.selected) {
        return $(this.el).addClass('selected');
      } else {
        return $(this.el).removeClass('selected');
      }
    }
  });
  window.ContactEditorView = Backbone.View.extend({
    events: {
      'click .addButton': 'addNewContact',
      'keypress input': 'addNewContactOnEnter',
      'click .deleteButton': 'deleteContacts',
      'click .inviteButton': 'inviteContacts'
    },
    initialize: function() {
      _.bindAll(this, "render");
      this.template = _.template($('#contact-list-template').html());
      this.collection.on('all', this.render);
      return this.contactViews = [];
    },
    render: function() {
      var $contacts, contactViews, self;
      self = this;
      $(this.el).html(this.template());
      $contacts = this.$('.contacts');
      contactViews = this.contactViews = [];
      this.collection.each(function(contact) {
        var view;
        view = new ContactEditorContactView({
          model: contact,
          collection: this.collection
        });
        view.on('selectionChanged', function(selected) {
          return self.childSelected(selected);
        });
        contactViews.push(view);
        return $contacts.append(view.render().el);
      });
      return this;
    },
    childSelected: function(selected) {
      var $enabledWhenSelectionButtons, selectedRows;
      $enabledWhenSelectionButtons = this.$('.enabledWhenUsersSelected');
      console.log(this);
      selectedRows = this.getSelectedRows();
      if (selectedRows.length > 0) {
        return $enabledWhenSelectionButtons.removeAttr('disabled');
      } else {
        return $enabledWhenSelectionButtons.attr('disabled', true);
      }
    },
    getSelectedRows: function() {
      var answer, contactView, index, _i, _len, _ref;
      answer = [];
      _ref = this.contactViews;
      for (index = _i = 0, _len = _ref.length; _i < _len; index = ++_i) {
        contactView = _ref[index];
        if (contactView.selected) {
          answer.push({
            index: index,
            model: contactView.model
          });
        }
      }
      return answer;
    },
    addNewContactOnEnter: function(event) {
      if (event.keyCode === 13) {
        return this.addNewContact(event);
      }
    },
    addNewContact: function(event) {
      var newContact, onError;
      event.preventDefault();
      this.$('.addButton').attr("disabled", true);
      this.$('.errorText').html("");
      newContact = {
        name: this.$(".nameInput").val(),
        phoneNumber: this.$(".numberInput").val()
      };
      onError = function(model, xhr, options) {
        var errorResult;
        errorResult = $.parseJSON(xhr.responseText);
        this.$('.errorText').html(errorResult.error);
        return this.$('.addButton').attr("disabled", false);
      };
      this.collection.create(newContact, {
        wait: true,
        error: onError
      });
      return false;
    },
    deleteContacts: function() {
      var model, row, selectedRows, _i, _len;
      selectedRows = this.getSelectedRows();
      for (_i = 0, _len = selectedRows.length; _i < _len; _i++) {
        row = selectedRows[_i];
        model = row.model;
        if (!model.get('isDefaultSender')) {
          model.destroy();
        }
      }
      return false;
    },
    inviteContacts: function() {
      var selectedIds, self;
      self = this;
      selectedIds = _.map(this.getSelectedRows(), function(row) {
        return row.model.id;
      });
      $.ajax({
        type: 'POST',
        url: '/api/invite',
        data: JSON.stringify(selectedIds),
        success: function(data, textStatus, xhr) {
          return showMessage(self.$('.errorText'), "" + data.length + " invite" + (data.length !== 1 ? "s" : "") + " sent.");
        },
        error: function(xhr, textStatus, errorThrown) {
          return apiErrorHandler(self.$('.errorText'), xhr);
        }
      });
      return false;
    }
  });
  window.LogView = Backbone.View.extend({
    initialize: function() {
      _.bindAll(this, "render");
      this.template = _.template($('#log-list-template').html());
      this.logEntryTemplate = _.template($('#log-entry-template').html());
      return this.collection.on('all', this.render);
    },
    render: function() {
      var self;
      self = this;
      $(this.el).html(this.template());
      this.renderLogEntries();
      return this;
    },
    renderLogEntries: function() {
      var $logEntries, now, self;
      self = this;
      $logEntries = this.$('.logEntries');
      $logEntries.empty();
      now = this.collection.now;
      this.collection.each(function(log) {
        var jsonLogEntry;
        jsonLogEntry = log.toJSON();
        jsonLogEntry.timeStr = formatTime(jsonLogEntry.time, now);
        return $logEntries.append(self.logEntryTemplate(jsonLogEntry));
      });
      return this;
    }
  });
  window.contacts = new window.Contacts();
  window.logEntries = new window.LogEntries();
  return window.XmppVoiceMail = Backbone.Router.extend({
    routes: {
      '': 'login',
      'main': 'main'
    },
    initialize: function() {
      this.loginView = new LoginView();
      this.$main = $('#main');
      this.contactEditorView = new ContactEditorView({
        collection: window.contacts
      });
      return this.logView = new LogView({
        collection: window.logEntries
      });
    },
    login: function() {
      this.$main.empty();
      return this.$main.append(this.loginView.render().el);
    },
    main: function() {
      window.contacts.fetch();
      window.logEntries.fetch();
      this.$main.empty();
      this.$main.append(this.contactEditorView.render().el);
      return this.$main.append(this.logView.render().el);
    }
  });
})(jQuery);