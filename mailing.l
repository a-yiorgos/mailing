#!/usr/bin/pil
# 24oct26 Software Lab. Alexander Burger

# Configuration
(setq
   *MailingList "picolisp@software-lab.de"
   *SpoolFile "/var/mail/picolisp"
   *MailingDomain "software-lab.de"
   *Mailings (make (in "Mailings" (while (line T) (link @))))
   *SmtpHost "smtp.strato.de"
   *SmtpPort 465
   *SmtpUser "picolisp@software-lab.de"
   *SmtpPW "XXXX" )

# Process mails
(loop
   (when (gt0 (car (info *SpoolFile)))
      (catch NIL
         (protect
            (in *SpoolFile
               (unless (= "From" (till " " T))
                  (msg '!! " Bad mbox file")
                  (throw) )
               (char)
               (while (setq *From (lowc (till " " T)))
                  (line)  # Skip rest of line and "\r\n"
                  (off
                     *Src *Subject *Date *MessageID *InReplyTo *MimeVersion
                     *ContentType *ContentTransferEncoding *ContentDisposition
                     *UserAgent )
                  (while (trim (split (line) " "))
                     (let L @
                        (while (and (sub? (peek) " \t") (char))  # Skip WSP
                           (conc L (trim (split (line) " "))) )
                        (setq *Line (glue " " (cdr L)))
                        (case (pack (car L))
                           ("From:" (setq *Src *Line))
                           ("Subject:" (setq *Subject *Line))
                           ("Date:" (setq *Date *Line))
                           ("Message-ID:" (setq *MessageID *Line))
                           ("In-Reply-To:" (setq *InReplyTo *Line))
                           ("MIME-Version:" (setq *MimeVersion *Line))
                           ("Content-Type:" (setq *ContentType *Line))
                           ("Content-Transfer-Encoding:" (setq *ContentTransferEncoding *Line))
                           ("Content-Disposition:" (setq *ContentDisposition *Line))
                           ("User-Agent:" (setq *UserAgent *Line)) ) ) )
                  (if (nor (member *From *Mailings) (= "subscribe" (lowc *Subject)))
                     (unless (= *From "mailer-daemon")
                        (out "/dev/null" (echo "\nFrom ") (msg *From " discarded")) )
                     (msg '** " " *From " " (stamp))
                     (unless (setq *Sock (pipe (exec "@bin/ssl" *SmtpHost *SmtpPort)))
                        (msg '!! " Can't connect to SMTP server")
                        (throw) )
                     (unless
                        (and
                           (pre? "220 " (in *Sock (line T)))
                           (out *Sock (prinl "HELO " *MailingDomain "\r"))
                           (pre? "250 " (in *Sock (line T)))
                           (out *Sock
                              (prin "AUTH PLAIN ")
                              (pipe
                                 (prog
                                    (prin *SmtpUser)
                                    (wr 0)
                                    (prin *SmtpUser)
                                    (wr 0)
                                    (prin *SmtpPW) )
                                 (prBase64 T "\r") )
                              (prinl "\r") )
                           (pre? "235 " (in *Sock (line T)))
                           (out *Sock (prinl "MAIL FROM:<" *MailingList ">\r"))
                           (pre? "250 " (in *Sock (line T))) )
                        (msg '!! " Can't HELO")
                        (throw) )
                     (when (= "subscribe" (lowc *Subject))
                        (push1 '*Mailings *From)
                        (out "Mailings" (mapc prinl *Mailings)) )
                     (for To *Mailings
                        (out *Sock (prinl "RCPT TO:" To "\r"))
                        (unless (pre? "250 " (in *Sock (line T)))
                           (msg To " can't mail") ) )
                     (out *Sock (prinl "DATA\r"))
                     (when (pre? "354 " (in *Sock (line T)))
                        (out *Sock
                           (prin "From: ")
                           (use (@N @M)
                              (if (match '(@N " " "<" @M ">") (chop *Src))
                                 (prinl @N " <" *MailingList ">\r")
                                 (prinl *MailingList "\r") ) )
                           (prinl "Sender: " (or *Src *From) "\r")
                           (prinl "Reply-To: " *MailingList "\r")
                           (prinl "To: " *MailingList "\r")
                           (prinl "Subject: " *Subject "\r")
                           (and *Date (prinl "Date: " @ "\r"))
                           (and *MessageID (prinl "Message-ID: " @ "\r"))
                           (and *InReplyTo (prinl "In-Reply-To: " @ "\r"))
                           (and *MimeVersion (prinl "MIME-Version: " @ "\r"))
                           (and *ContentType (prinl "Content-Type: " @ "\r"))
                           (and *ContentTransferEncoding (prinl "Content-Transfer-Encoding: " @ "\r"))
                           (and *ContentDisposition (prinl "Content-Disposition: " @ "\r"))
                           (and *UserAgent (prinl "User-Agent: " @ "\r"))
                           (prinl "\r")
                           (cond
                              ((= "subscribe" (lowc *Subject))
                                 (prinl "Hello " (or *Src *From) " :-)\r")
                                 (prinl "You are now subscribed\r")
                                 (prinl "****\r\n\r") )
                              ((= "unsubscribe" (lowc *Subject))
                                 (out "Mailings"
                                    (mapc prinl (del *From '*Mailings)) )
                                 (prinl "Good bye " (or *Src *From) " :-(\r")
                                 (prinl "You are now unsubscribed\r")
                                 (prinl "****\r\n\r") ) )
                           (echo "\nFrom ")
                           (prinl "\n-- \r")
                           (prinl "Fridays for Functions: 9:00-17:00 UTC")
                           (prinl "on Jitsi https://meeting.itship.ch/picolisp")
                           (prinl)
                           (prinl "UNSUBSCRIBE: mailto:" *MailingList "?subject=Unsubscribe\r")
                           (prinl ".\r")
                           (prinl "QUIT\r") ) )
                     (close *Sock) ) ) )
            (out *SpoolFile (rewind)) ) ) )
   (call "fetchmail" "-as")
   (wait `(* 4 60 1000)) )
