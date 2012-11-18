(function($) {
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
  window.ContactView = Backbone.View.extend({
    tagName: 'li',
    className: 'listItem',
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
      'click .deleteButton': 'deleteContacts'
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
      var deleteButton, selectedRows;
      deleteButton = this.$('deleteButton');
      console.log(this);
      selectedRows = this.getSelectedRows();
      if (selectedRows.length > 0) {
        return this.$('.deleteButton').removeAttr('disabled');
      } else {
        return this.$('.deleteButton').attr('disabled', true);
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
    addNewContact: function() {
      var newContact, onError;
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
      return this.collection.create(newContact, {
        wait: true,
        error: onError
      });
    },
    deleteContacts: function() {
      var model, row, selectedRows, _i, _len, _results;
      selectedRows = this.getSelectedRows();
      _results = [];
      for (_i = 0, _len = selectedRows.length; _i < _len; _i++) {
        row = selectedRows[_i];
        model = row.model;
        if (!model.get('isDefaultSender')) {
          _results.push(model.destroy());
        } else {
          _results.push(void 0);
        }
      }
      return _results;
    }
  });
  window.contacts = new window.Contacts();
  return window.XmppVoiceMail = Backbone.Router.extend({
    routes: {
      '': 'contactEditor'
    },
    initialize: function() {
      this.contactEditorView = new ContactEditorView({
        collection: window.contacts
      });
      return contacts.fetch();
    },
    contactEditor: function() {
      var $main;
      $main = $('#main');
      $main.empty();
      return $main.append(this.contactEditorView.render().el);
    }
  });
})(jQuery);